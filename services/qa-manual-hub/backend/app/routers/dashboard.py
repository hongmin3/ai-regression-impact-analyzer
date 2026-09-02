"""Dashboard, recent updates, audit log listing and settings read-out."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .. import audit as audit_actions
from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    AuditLog,
    Document,
    DocumentVersion,
    Product,
    StoredFile,
    User,
)
from ..schemas import (
    ActivityEntry,
    AuditOut,
    DashboardCounts,
    DashboardOut,
    RecentUpload,
    SettingsOut,
)
from ..services import document_row_select, rows_from
from ..storage import get_storage

router = APIRouter(prefix="/api", tags=["dashboard"])

APP_VERSION = "1.0.0"


def _activity(entry: AuditLog) -> ActivityEntry:
    return ActivityEntry(
        id=entry.id,
        created_at=entry.created_at,
        action=entry.action,
        action_label=audit_actions.ACTION_LABELS_KO.get(entry.action, entry.action),
        actor_display_name=entry.actor_display_name,
        actor_login_id=entry.actor_login_id,
        product_name=entry.product_name,
        document_name=entry.document_name,
        version_label=entry.version_label,
        target_label=entry.target_label,
        detail=entry.detail,
    )


def _recent_uploads(db: DbSession, limit: int) -> list[RecentUpload]:
    stmt = (
        select(DocumentVersion, Document, Product)
        .join(Document, Document.id == DocumentVersion.document_id)
        .join(Product, Product.id == Document.product_id)
        .order_by(DocumentVersion.upload_date.desc())
        .limit(limit)
    )
    out: list[RecentUpload] = []
    for version, document, product in db.execute(stmt):
        out.append(
            RecentUpload(
                version_id=version.id,
                document_id=document.id,
                document_name=document.name,
                product_id=product.id,
                product_name=product.name,
                version_label=version.label,
                revision=version.revision,
                version=version.version,
                uploaded_by_display_name=version.uploaded_by_display_name,
                upload_date=version.upload_date,
                is_current=document.current_version_id == version.id,
            )
        )
    return out


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: DbSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DashboardOut:
    counts = DashboardCounts(
        products=db.scalar(select(func.count(Product.id))) or 0,
        products_active=db.scalar(
            select(func.count(Product.id)).where(Product.is_active.is_(True))
        )
        or 0,
        documents=db.scalar(select(func.count(Document.id))) or 0,
        documents_active=db.scalar(
            select(func.count(Document.id)).where(Document.status == STATUS_ACTIVE)
        )
        or 0,
        documents_archived=db.scalar(
            select(func.count(Document.id)).where(Document.status == STATUS_ARCHIVED)
        )
        or 0,
        documents_with_current=db.scalar(
            select(func.count(Document.id)).where(
                Document.current_version_id.isnot(None),
                Document.status == STATUS_ACTIVE,
            )
        )
        or 0,
        versions=db.scalar(select(func.count(DocumentVersion.id))) or 0,
        users_active=db.scalar(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
        or 0,
        storage_bytes=db.scalar(select(func.coalesce(func.sum(StoredFile.byte_size), 0)))
        or 0,
    )

    current_changes = [
        _activity(e)
        for e in db.scalars(
            select(AuditLog)
            .where(AuditLog.action == audit_actions.CURRENT_VERSION_CHANGE)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(10)
        )
    ]
    recent_activity = [
        _activity(e)
        for e in db.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(15)
        )
    ]
    recent_documents = rows_from(
        db,
        document_row_select()
        .where(Document.status == STATUS_ACTIVE)
        .order_by(Document.created_at.desc())
        .limit(8),
    )

    return DashboardOut(
        counts=counts,
        recent_uploads=_recent_uploads(db, 10),
        recent_current_changes=current_changes,
        recent_documents=recent_documents,
        recent_activity=recent_activity,
    )


@router.get("/recent-updates", response_model=list[RecentUpload])
def recent_updates(
    limit: int = Query(default=50, ge=1, le=300),
    db: DbSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RecentUpload]:
    return _recent_uploads(db, limit)


@router.get("/audit-logs", response_model=list[AuditOut])
def audit_logs(
    action: str | None = Query(default=None, max_length=64),
    actor: str | None = Query(default=None, max_length=128),
    product_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: DbSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AuditOut]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action.strip().upper())
    if actor:
        needle = f"%{actor.strip().lower()}%"
        stmt = stmt.where(
            func.lower(func.coalesce(AuditLog.actor_display_name, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.actor_login_id, "")).like(needle)
        )
    if product_id:
        stmt = stmt.where(AuditLog.product_id == product_id)
    if document_id:
        stmt = stmt.where(AuditLog.document_id == document_id)
    if date_from:
        stmt = stmt.where(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(AuditLog.created_at) <= date_to)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(func.coalesce(AuditLog.document_name, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.product_name, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.version_label, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.target_label, "")).like(needle)
            | func.lower(func.coalesce(AuditLog.detail, "")).like(needle)
        )

    stmt = (
        stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )

    out: list[AuditOut] = []
    for entry in db.scalars(stmt):
        item = AuditOut.model_validate(entry)
        item.action_label = audit_actions.ACTION_LABELS_KO.get(
            entry.action, entry.action
        )
        out.append(item)
    return out


@router.get("/audit-actions", response_model=dict[str, str])
def audit_action_labels(_: User = Depends(get_current_user)) -> dict[str, str]:
    return dict(audit_actions.ACTION_LABELS_KO)


@router.get("/settings", response_model=SettingsOut)
def read_settings(_: User = Depends(get_current_user)) -> SettingsOut:
    return SettingsOut(
        max_upload_mb=settings.max_upload_mb,
        allowed_extensions=sorted(settings.allowed_extension_set),
        session_lifetime_hours=settings.session_lifetime_hours,
        password_min_length=settings.password_min_length,
        storage_root=str(settings.storage_root),
        storage_backend=get_storage().backend_name,
        app_version=APP_VERSION,
    )
