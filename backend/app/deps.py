"""Authentication dependencies.

Auth is a server-side session plus an opaque HttpOnly cookie.  Any request to a
protected endpoint without a live session gets 401; the SPA turns that into a
redirect to the login screen.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .config import settings
from .db import get_db
from .models import Session as SessionModel
from .models import User
from .security import hash_session_token, new_session_token, session_expiry

# Sliding expiry: only touched when more than this much of the window has
# elapsed, so a busy tab does not write to the DB on every request.
_REFRESH_AFTER = timedelta(minutes=15)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="로그인이 필요합니다.",
)


def create_session(
    db: DbSession, user: User, request: Request, response: Response
) -> SessionModel:
    token = new_session_token()
    now = datetime.now(UTC)
    record = SessionModel(
        token_hash=hash_session_token(token),
        user_id=user.id,
        created_at=now,
        expires_at=session_expiry(now),
        last_seen_at=now,
        ip_address=(request.client.host[:64] if request.client else None),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )
    db.add(record)
    db.flush()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_lifetime_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
        path="/",
    )
    return record


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
    )


def revoke_session(db: DbSession, token: str) -> SessionModel | None:
    record = db.scalar(
        select(SessionModel).where(
            SessionModel.token_hash == hash_session_token(token)
        )
    )
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
    return record


def _load_session(db: DbSession, token: str) -> SessionModel | None:
    record = db.scalar(
        select(SessionModel).where(
            SessionModel.token_hash == hash_session_token(token)
        )
    )
    if record is None or record.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if record.expires_at <= now:
        return None
    return record


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise CREDENTIALS_ERROR

    record = _load_session(db, token)
    if record is None:
        raise CREDENTIALS_ERROR

    user = record.user
    if user is None or not user.is_active:
        # A user disabled mid-session loses access on the next request.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요.",
        )

    now = datetime.now(UTC)
    if now - record.last_seen_at > _REFRESH_AFTER:
        record.last_seen_at = now
        record.expires_at = session_expiry(now)
        db.commit()

    request.state.current_user = user
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user


def require_password_current(user: User = Depends(get_current_user)) -> User:
    """Block normal work while a forced password change is outstanding.

    Applied to mutating document/product endpoints, not to ``/auth/me`` or the
    change-password endpoint itself, so the user can always get unstuck.
    """
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="비밀번호를 먼저 변경해야 합니다.",
        )
    return user
