from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.product_config import list_product_configs
from app.core.storage import Storage
from app.modules.manual_review.comment_writer import insert_comments, output_filename
from app.modules.manual_review.comment_resolution import suggest_prior_comments
from app.modules.manual_review.reviewer import MANUAL_REVIEW_STAGES, ManualRevisionReviewer
from app.modules.manual_review.schemas import JUDGMENT_LABELS_KO, ManualJudgment

JUDGMENT_OPTIONS = [(item.value, JUDGMENT_LABELS_KO[item]) for item in ManualJudgment]

router = APIRouter()
templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", get_settings().root / "app" / "web" / "templates"])
templates.env.filters["judgment_ko"] = lambda value: JUDGMENT_LABELS_KO.get(value, value or "-")
storage = Storage()


def _srs_status_by_product(products: list[str]) -> dict[str, dict]:
    return {
        product: {
            "documents": storage.active_documents("specification", product),
            "latest_sync": storage.latest_sync(product, "specification"),
        }
        for product in products
    }


def _manual_types_by_product(products: list[str], revisions: list[dict]) -> dict[str, list[str]]:
    values = {product: set() for product in products}
    for config in list_product_configs():
        values.setdefault(config.product, set()).update(config.manual_types)
    for revision in revisions:
        values.setdefault(revision["product"], set()).add(revision["manual_name"])
    return {product: sorted(names) for product, names in values.items()}


def _normalize_target_version(value: str) -> str:
    return value.strip().removeprefix("V").removeprefix("v").strip()


def _revision_label(target_version: str, parent_round: int | None, pdf_baseline: bool = False) -> str:
    suffix = "Baseline" if pdf_baseline else f"W{(parent_round + 2) if parent_round is not None else 1}"
    return f"V{target_version} · {suffix}"


@router.get("", response_class=HTMLResponse)
def home(request: Request):
    products = storage.list_products()
    revisions = storage.list_manual_revisions()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "products": products,
            "revisions": revisions,
            "srs_status_by_product": _srs_status_by_product(products),
            "manual_types_by_product": _manual_types_by_product(products, revisions),
            "versions_by_product": {product: storage.list_versions(product) for product in products},
        },
    )


@router.get("/guide", response_class=HTMLResponse)
def guide(request: Request):
    return templates.TemplateResponse(request, "guide.html", {})


def _run_job(
    job_id: str,
    path: Path,
    product: str,
    manual_name: str,
    revision_label: str,
    parent_revision_id: int | None,
    release_note_path: Path | None = None,
    design_review_path: Path | None = None,
    target_version: str = "",
) -> None:
    try:
        storage.update_analysis(job_id, "RUNNING")
        reviewer = ManualRevisionReviewer(storage=storage)
        result = reviewer.run(
            path, product, manual_name, revision_label,
            parent_revision_id=parent_revision_id, analysis_id=job_id,
            release_note_path=release_note_path, design_review_path=design_review_path,
            target_version=target_version,
        )
        storage.update_analysis(job_id, "DONE", result=result)
    except Exception as exc:
        storage.update_analysis(job_id, "FAILED", error=str(exc))


def _register_or_reuse_reference_doc(kind: str, product: str, revision_label: str, upload: UploadFile | None) -> Path | None:
    """Release Note/설계검토보고서가 이번에 업로드됐으면 등록하고, 아니면 이 제품에 이미
    등록된 가장 최근 문서를 자동으로 사용한다 (스펙 §45 "사용자 개입 최소화")."""
    if upload and upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in (".pdf", ".docx"):
            raise HTTPException(400, f"지원하지 않는 파일 형식입니다: {suffix}")
        path = get_settings().path("storage.manual_revision_dir") / f"{uuid.uuid4().hex}{suffix}"
        with path.open("wb") as target:
            shutil.copyfileobj(upload.file, target)
        storage.add_document(kind, product, revision_label, "", upload.filename, path)
        return path
    existing = storage.active_documents(kind, product)
    return Path(existing[-1]["path"]) if existing else None


@router.post("/revisions")
def start_revision(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    product: str = Form(...),
    manual_name: str = Form(...),
    target_version: str = Form(...),
    parent_revision_id: str = Form(""),
    release_note_file: UploadFile | None = File(None),
    design_review_file: UploadFile | None = File(None),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        raise HTTPException(400, "Word Track Changes(.docx) 또는 PDF 파일만 지원합니다.")
    product = product.strip()
    manual_name = manual_name.strip()
    target_version = _normalize_target_version(target_version)
    if not product or not manual_name or not target_version:
        raise HTTPException(400, "제품, Manual 종류, 제품 버전을 모두 입력하세요.")
    if product not in storage.list_products():
        raise HTTPException(400, "등록되지 않은 제품입니다. 공용 Knowledge에서 제품을 먼저 추가하세요.")
    storage.ensure_version(product, target_version)
    try:
        parent_id = int(parent_revision_id) if parent_revision_id.strip() else None
    except ValueError as exc:
        raise HTTPException(400, "이전 검증 값이 올바르지 않습니다.") from exc
    parent = storage.get_manual_revision(parent_id) if parent_id else None
    if parent_id and not parent:
        raise HTTPException(400, "선택한 이전 검증을 찾을 수 없습니다.")
    if parent and (parent["product"] != product or parent["manual_name"] != manual_name):
        raise HTTPException(400, "이전 Round는 같은 제품과 Manual 종류에서만 선택할 수 있습니다.")
    if parent and parent["target_version"] and parent["target_version"] != target_version:
        raise HTTPException(400, "같은 검증 계보에서는 제품 버전을 변경할 수 없습니다. 새 제품 버전은 이전 Round를 선택하지 않고 시작하세요.")
    next_round = int(parent["round_number"]) + 1 if parent else 0
    revision_label = _revision_label(target_version, int(parent["round_number"]) if parent else None, suffix == ".pdf" and not parent)
    path = get_settings().path("storage.manual_revision_dir") / f"{uuid.uuid4().hex}{suffix}"
    with path.open("wb") as target:
        shutil.copyfileobj(file.file, target)
    release_note_path = _register_or_reuse_reference_doc("release_note", product, revision_label, release_note_file)
    design_review_path = _register_or_reuse_reference_doc("design_review", product, revision_label, design_review_file)
    job_id = uuid.uuid4().hex[:12]
    storage.create_analysis(job_id, stage_total=len(MANUAL_REVIEW_STAGES), module="manual_review")
    background_tasks.add_task(_run_job, job_id, path, product, manual_name, revision_label, parent_id, release_note_path, design_review_path, target_version)
    return {"job_id": job_id, "status_url": f"/manual-review/jobs/{job_id}"}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = storage.get_analysis(job_id)
    if not job:
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return job


@router.get("/jobs/{job_id}/stream")
async def job_status_stream(job_id: str):
    if not storage.get_analysis(job_id):
        raise HTTPException(404, "작업을 찾을 수 없습니다.")

    async def event_source():
        last_payload = None
        while True:
            job = storage.get_analysis(job_id)
            if not job:
                break
            payload = json.dumps(job, ensure_ascii=False, default=str)
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job["status"] in ("DONE", "FAILED"):
                break
            await asyncio.sleep(0.7)

    return StreamingResponse(event_source(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/revisions/{revision_id}/view", response_class=HTMLResponse)
def view_revision(request: Request, revision_id: int):
    revision = storage.get_manual_revision(revision_id)
    if not revision:
        raise HTTPException(404, "리비전을 찾을 수 없습니다.")
    changes = storage.list_manual_changes(revision_id)
    prior_open_comments = storage.list_open_comments_for_revision(revision["parent_revision_id"]) if revision["parent_revision_id"] else []
    prior_open_comments = suggest_prior_comments(prior_open_comments, changes)
    release_findings = storage.list_release_findings(revision_id)
    cross_manual_impacts = storage.list_cross_manual_impacts(revision_id)
    return templates.TemplateResponse(
        request,
        "revision.html",
        {
            "revision": revision,
            "changes": changes,
            "prior_open_comments": prior_open_comments,
            "decision_counts": _decision_counts(changes),
            "judgment_options": JUDGMENT_OPTIONS,
            "missing_findings": [f for f in release_findings if f["status"] == "MISSING_SUSPECTED"],
            "cross_manual_impacts": cross_manual_impacts,
        },
    )


@router.post("/revisions/{revision_id}/cross-manual/{impact_id}/status")
def set_cross_manual_status(revision_id: int, impact_id: int, qa_status: str = Form(...)):
    impacts = {item["id"] for item in storage.list_cross_manual_impacts(revision_id)}
    if impact_id not in impacts:
        raise HTTPException(404, "다른 Manual 영향 후보를 찾을 수 없습니다.")
    if qa_status not in {"REVIEW_REQUIRED", "IMPACT_CONFIRMED", "NO_IMPACT"}:
        raise HTTPException(400, "지원하지 않는 QA 상태입니다.")
    storage.update_cross_manual_impact_status(impact_id, qa_status)
    return RedirectResponse(f"/manual-review/revisions/{revision_id}/view", status_code=303)


def _decision_counts(changes: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for change in changes:
        if not change["functional"]:
            continue
        key = change["decision"] or "판정 대기"
        counts[key] = counts.get(key, 0) + 1
    return counts


@router.post("/revisions/{revision_id}/changes/{change_id}/qa-decision")
def set_qa_decision(revision_id: int, change_id: int, qa_decision: str = Form(...), qa_note: str = Form("")):
    change = storage.get_manual_change(change_id)
    if not change or change["revision_id"] != revision_id:
        raise HTTPException(404, "변경 항목을 찾을 수 없습니다.")
    storage.update_manual_change_qa_decision(change_id, qa_decision, qa_note)
    return RedirectResponse(f"/manual-review/revisions/{revision_id}/view", status_code=303)


@router.post("/revisions/{revision_id}/comments/{comment_id}/status")
def set_comment_status(revision_id: int, comment_id: int, status: str = Form(...)):
    revision = storage.get_manual_revision(revision_id)
    comment = storage.get_manual_comment(comment_id)
    allowed = {"RESOLVED", "NOT_RESOLVED", "REOPENED", "IGNORED_BY_QA"}
    carried_ids = {
        item["id"] for item in storage.list_open_comments_for_revision(revision["parent_revision_id"])
    } if revision and revision["parent_revision_id"] else set()
    if not revision or not comment or comment_id not in carried_ids:
        raise HTTPException(404, "이전 Round Comment를 찾을 수 없습니다.")
    if status not in allowed:
        raise HTTPException(400, "지원하지 않는 Comment 상태입니다.")
    resolved_in = revision_id if status == "RESOLVED" else None
    storage.update_manual_comment_status(comment_id, status, resolved_in_revision_id=resolved_in)
    return RedirectResponse(f"/manual-review/revisions/{revision_id}/view", status_code=303)


@router.get("/revisions/{revision_id}/comment-docx")
def download_comment_docx(revision_id: int):
    """QA 검토 결과를 반영해 문제 항목마다 Word Comment를 삽입한 DOCX를 생성해 내려준다
    (스펙 §25). 원본 Track Changes/기존 Comment는 건드리지 않고 새 Comment만 추가한다."""
    revision = storage.get_manual_revision(revision_id)
    if not revision:
        raise HTTPException(404, "리비전을 찾을 수 없습니다.")
    source_path = Path(revision["source_path"])
    if not source_path.exists():
        raise HTTPException(404, "원본 리비전 파일을 찾을 수 없습니다.")
    if source_path.suffix.lower() != ".docx":
        raise HTTPException(400, "Word Comment 삽입은 DOCX 리비전에서만 사용할 수 있습니다.")
    changes = storage.list_manual_changes(revision_id)
    filename = output_filename(revision["manual_name"], revision["revision_label"])
    output_path = get_settings().path("storage.manual_review_comment_dir") / f"{revision_id}-{filename}"
    inserted = insert_comments(source_path, changes, output_path, author=f"{revision['product']} QA AI")
    if inserted == 0:
        raise HTTPException(400, "Comment를 삽입할 문제 항목이 없습니다 (모든 변경이 문제없음이거나 분석 대상이 아닙니다).")
    return FileResponse(output_path, filename=filename)
