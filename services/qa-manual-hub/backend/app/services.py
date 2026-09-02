"""Query helpers shared by the document, search and dashboard routers."""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession, aliased

from .models import (
    Document,
    DocumentCategory,
    DocumentVersion,
    Product,
    StoredFile,
    User,
)
from .schemas import DocumentOut, DocumentRow, VersionOut
from .storage import is_inline_previewable

CurrentVersion = aliased(DocumentVersion, name="current_version")
CreatedBy = aliased(User, name="created_by_user")
UpdatedBy = aliased(User, name="updated_by_user")


def document_row_select() -> Select:
    """One statement that produces everything the document tables display.

    Joining the current version here (rather than lazily per row) keeps the
    product detail page at a single query no matter how many documents it lists.
    """
    version_counts = (
        select(
            DocumentVersion.document_id.label("did"),
            func.count(DocumentVersion.id).label("ver_count"),
        )
        .group_by(DocumentVersion.document_id)
        .subquery()
    )
    return (
        select(
            Document,
            Product.name,
            DocumentCategory.name,
            DocumentCategory.sort_order,
            CurrentVersion,
            CreatedBy.display_name,
            UpdatedBy.display_name,
            func.coalesce(version_counts.c.ver_count, 0),
        )
        .join(Product, Product.id == Document.product_id)
        .join(DocumentCategory, DocumentCategory.id == Document.category_id)
        .outerjoin(CurrentVersion, CurrentVersion.id == Document.current_version_id)
        .outerjoin(CreatedBy, CreatedBy.id == Document.created_by)
        .outerjoin(UpdatedBy, UpdatedBy.id == Document.updated_by)
        .outerjoin(version_counts, version_counts.c.did == Document.id)
    )


def build_document_row(
    document: Document,
    product_name: str,
    category_name: str,
    category_sort_order: int,
    current: DocumentVersion | None,
    created_by_name: str | None,
    updated_by_name: str | None,
    version_count: int,
) -> DocumentRow:
    # The joined columns are not attributes on the ORM object, so the base
    # fields are validated from it and the rest are supplied explicitly.
    row = DocumentRow(
        **DocumentOut.model_validate(document).model_dump(),
        product_name=product_name,
        category_name=category_name,
        category_sort_order=category_sort_order,
        version_count=version_count,
        created_by_display_name=created_by_name,
        updated_by_display_name=updated_by_name,
    )
    if current is not None:
        row.current_version_id = current.id
        row.current_revision = current.revision
        row.current_version_label = current.label
        row.current_document_number = current.document_number
        row.current_language = current.language
        row.revision_date = current.revision_date
        row.uploaded_by_display_name = current.uploaded_by_display_name
        row.upload_date = current.upload_date
    return row


def rows_from(db: DbSession, stmt: Select) -> list[DocumentRow]:
    return [build_document_row(*record) for record in db.execute(stmt)]


def version_out(
    version: DocumentVersion, current_version_id: uuid.UUID | None
) -> VersionOut:
    out = VersionOut.model_validate(version)
    out.is_current = current_version_id == version.id
    out.can_preview = is_inline_previewable(version.stored_file.file_extension)
    return out


def versions_out(
    versions: Iterable[DocumentVersion], current_version_id: uuid.UUID | None
) -> list[VersionOut]:
    return [version_out(v, current_version_id) for v in versions]


def find_duplicates(
    db: DbSession, sha256: str, *, exclude_file_id: uuid.UUID | None = None
) -> Sequence[tuple[StoredFile, DocumentVersion | None, Document | None, Product | None]]:
    """Locate every place a file with this content is already registered.

    Used to warn (never to block) on upload -- the same PDF legitimately shows up
    as a separate version in real document workflows.
    """
    stmt = (
        select(StoredFile, DocumentVersion, Document, Product)
        .outerjoin(DocumentVersion, DocumentVersion.stored_file_id == StoredFile.id)
        .outerjoin(Document, Document.id == DocumentVersion.document_id)
        .outerjoin(Product, Product.id == Document.product_id)
        .where(StoredFile.sha256 == sha256)
        .order_by(StoredFile.created_at)
    )
    if exclude_file_id is not None:
        stmt = stmt.where(StoredFile.id != exclude_file_id)
    return list(db.execute(stmt).all())
