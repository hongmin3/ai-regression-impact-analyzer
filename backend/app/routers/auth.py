"""Login / logout / my-account."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .. import audit
from ..config import settings
from ..db import get_db
from ..deps import (
    clear_session_cookie,
    create_session,
    get_current_user,
    revoke_session,
)
from ..models import LoginHistory, User
from ..schemas import ChangePasswordRequest, LoginRequest, MeOut, Message
from ..security import (
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Deliberately identical for "no such user" and "wrong password" (spec 50).
_GENERIC_LOGIN_ERROR = "아이디 또는 비밀번호가 올바르지 않습니다."


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        login_id=user.login_id,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        is_admin=user.is_admin,
    )


@router.post("/login", response_model=MeOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> MeOut:
    login_id = payload.login_id.strip()
    user = db.scalar(
        select(User).where(func.lower(User.login_id) == login_id.lower())
    )

    def _fail(reason: str) -> HTTPException:
        db.add(
            LoginHistory(
                login_id_attempted=login_id[:64],
                user_id=user.id if user else None,
                success=False,
                reason=reason,
                ip_address=audit.client_ip(request),
                user_agent=audit.user_agent(request),
            )
        )
        audit.record(
            db,
            action=audit.LOGIN_FAILURE,
            actor=None,
            actor_login_id=login_id[:64],
            request=request,
            target_user=user,
            target_label=login_id[:64],
            detail=reason,
        )
        db.commit()
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR
        )

    if user is None:
        raise _fail("unknown_login_id")

    if not verify_password(payload.password, user.password_hash):
        raise _fail("bad_password")

    if not user.is_active:
        # Same message to the client, distinct reason in the log.
        raise _fail("inactive_user")

    # Transparently upgrade the stored hash if Argon2 parameters have moved on.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    now = datetime.now(UTC)
    user.last_login_at = now
    create_session(db, user, request, response)
    db.add(
        LoginHistory(
            login_id_attempted=login_id[:64],
            user_id=user.id,
            success=True,
            reason=None,
            ip_address=audit.client_ip(request),
            user_agent=audit.user_agent(request),
        )
    )
    audit.record(db, action=audit.LOGIN, actor=user, request=request)
    db.commit()
    return _me(user)


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
) -> Message:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        record = revoke_session(db, token)
        if record is not None and record.user is not None:
            audit.record(
                db, action=audit.LOGOUT, actor=record.user, request=request
            )
        db.commit()
    clear_session_cookie(response)
    return Message(detail="로그아웃되었습니다.")


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return _me(user)


@router.post("/change-password", response_model=Message)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 비밀번호가 현재 비밀번호와 같습니다.",
        )
    if err := validate_password_strength(payload.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.updated_by = user.id
    audit.record(
        db,
        action=audit.USER_PASSWORD_CHANGE,
        actor=user,
        request=request,
        target_user=user,
        detail="본인 비밀번호 변경",
    )
    db.commit()
    return Message(detail="비밀번호가 변경되었습니다.")
