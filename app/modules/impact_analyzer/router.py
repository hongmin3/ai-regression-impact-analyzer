from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings, reload_settings
from app.core.storage import Storage
from app.modules.impact_analyzer.regression_analyzer import RegressionAnalyzer
from app.modules.impact_analyzer.schemas import ANALYSIS_STAGES
from app.parsers.document_parser import parse_document

router = APIRouter()
templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", get_settings().root / "app" / "web" / "templates"])
storage = Storage()


def _versions_by_product() -> dict[str, list[str]]:
    return {product: storage.list_versions(product) for product in storage.list_products()}


def _today_start_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def daily_token_status() -> dict:
    limit = int(get_settings().get("analysis.daily_token_limit", 0) or 0)
    used = storage.tokens_used_since(_today_start_iso())
    return {"used": used, "limit": limit, "exceeded": limit > 0 and used >= limit}


def _grouped_by_product_version(kind: str) -> list[dict]:
    """list_documents는 id 내림차순이라 각 그룹의 첫 항목이 가장 최근 등록분이다. 표시 순서일 뿐 검색 포함 여부와는 무관하다 (모두 active_documents 대상)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for document in storage.list_documents(kind):
        groups.setdefault((document["product"], document["version"]), []).append(document)
    return [
        {"product": product, "version": version, "documents": documents}
        for (product, version), documents in groups.items()
    ]


def _save_upload(upload: UploadFile, directory: Path, allowed: set[str]) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"지원하지 않는 파일 형식입니다: {suffix}")
    path = directory / f"{uuid.uuid4().hex}{suffix}"
    with path.open("wb") as target:
        shutil.copyfileobj(upload.file, target)
    return path


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    products = [p for p in storage.list_products() if storage.active_documents("specification", p) and storage.active_documents("testcase", p)]
    return templates.TemplateResponse(request, "index.html", {"products": products})


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request):
    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "spec_groups": _grouped_by_product_version("specification"),
            "testcase_groups": _grouped_by_product_version("testcase"),
            "products": storage.list_products(),
            "versions_by_product": _versions_by_product(),
            "spec_sync": storage.latest_sync("VXvue", "specification"),
        },
    )


@router.get("/guide", response_class=HTMLResponse)
def guide(request: Request):
    return templates.TemplateResponse(request, "guide.html", {})


@router.get("/analyses", response_class=HTMLResponse)
def analysis_history(request: Request):
    analyses = storage.list_analyses()
    for item in analyses:
        result = item.get("result") or {}
        decisions = result.get("decisions") or []
        item["recommended_count"] = sum(bool(decision.get("recommended")) for decision in decisions)
        item["impact_counts"] = {
            impact: sum(decision.get("impact") == impact for decision in decisions)
            for impact in ("HIGH", "MEDIUM", "LOW", "NONE")
        }
    return templates.TemplateResponse(request, "analyses.html", {"analyses": analyses})


@router.post("/knowledge/specification")
def register_specification(file: UploadFile = File(...), product: str = Form(...), version: str = Form("")):
    settings = get_settings()
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    path = _save_upload(file, settings.path("storage.specification_dir"), {".pdf", ".docx"})
    chunks = parse_document(path, path.stem)
    storage.add_document("specification", product, version, "", file.filename or path.name, path, {"chunk_count": len(chunks)})
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/testcase")
def register_testcase(file: UploadFile = File(...), product: str = Form(...), version: str = Form("")):
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    path = _save_upload(file, get_settings().path("storage.testcase_dir"), {".xlsx"})
    storage.add_document("testcase", product, version, "", file.filename or path.name, path)
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/delete/{document_id}")
def delete_document(document_id: int):
    document = storage.get_document(document_id)
    if not document:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    storage.delete_document(document_id)
    path = Path(document["path"])
    if path.exists():
        path.unlink()
    return RedirectResponse("/knowledge", status_code=303)


@router.get("/knowledge/documents")
def list_documents_json(kind: str, product: str):
    """동기화 스크립트가 원격 서버의 기존 등록 문서를 조회하기 위한 최소 JSON API."""
    return [{"id": doc["id"], "name": doc["name"]} for doc in storage.active_documents(kind, product)]


@router.post("/knowledge/sync-log")
def record_sync_log(product: str = Form(...), kind: str = Form(...), source: str = Form(...), status: str = Form(...), detail: str = Form("")):
    """원격에서 실행된 동기화 스크립트(scripts/sync_vxvue_spec.py 등)가 결과를 보고하는 용도."""
    sync_id = storage.sync_start(product, kind, source)
    storage.sync_finish(sync_id, status, detail)
    return {"ok": True}


@router.post("/knowledge/sync/specification")
def trigger_specification_sync():
    from app.modules.impact_analyzer.vxvue_spec_sync import is_available_on_this_host
    from app.modules.impact_analyzer.vxvue_spec_sync import run as run_spec_sync

    product = "VXvue"
    if storage.is_sync_running(product, "specification"):
        raise HTTPException(409, "이미 사양서 동기화가 진행 중입니다.")
    if not is_available_on_this_host():
        raise HTTPException(400, "이 서버에서는 ALM 크롤러 output 폴더에 접근할 수 없습니다. 크롤러가 있는 Windows PC에서 scripts/sync_vxvue_spec.py를 실행하세요.")
    sync_id = storage.sync_start(product, "specification", "alm_crawler")
    try:
        port = get_settings().get("app.port", 12000)
        result = run_spec_sync(f"http://127.0.0.1:{port}")
        storage.sync_finish(sync_id, result["status"], result["detail"])
        return result
    except Exception as exc:
        storage.sync_finish(sync_id, "FAILED", str(exc))
        raise HTTPException(500, f"동기화 실패: {exc}")


@router.get("/knowledge/download/{document_id}")
def download_document(document_id: int):
    document = storage.get_document(document_id)
    if not document:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    path = Path(document["path"])
    if not path.exists():
        raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=document["name"])


def _run_job(job_id: str, changes: list[Path], product: str, notes: str) -> None:
    try:
        storage.update_analysis(job_id, "RUNNING")
        result = RegressionAnalyzer().run_for_product(changes, product, analysis_id=job_id, user_notes=notes)
        storage.update_analysis(job_id, "DONE", result=result.model_dump(mode="json"))
    except Exception as exc:
        storage.update_analysis(job_id, "FAILED", error=str(exc))


@router.post("/analyses")
def start_analysis(background_tasks: BackgroundTasks, product: str = Form(...), notes: str = Form(""), change_files: list[UploadFile] = File(default=[])):
    notes = notes.strip()
    uploads = [f for f in change_files if f and f.filename]
    if not uploads and not notes:
        raise HTTPException(400, "변경문서를 첨부하거나 요청 사항을 입력하세요.")
    token_status = daily_token_status()
    if token_status["exceeded"]:
        raise HTTPException(429, f"오늘 Gemini 누적 토큰 사용량({token_status['used']:,})이 설정한 한도({token_status['limit']:,})를 초과해 분석을 실행할 수 없습니다. config.yaml의 analysis.daily_token_limit을 조정하세요.")
    if not storage.active_documents("specification", product) or not storage.active_documents("testcase", product):
        raise HTTPException(404, f"'{product}' 제품에 등록된 사양서 또는 TC가 없습니다. Knowledge 메뉴에서 먼저 등록하세요.")
    changes = [_save_upload(f, get_settings().path("storage.upload_dir"), {".pdf", ".docx"}) for f in uploads]
    job_id = uuid.uuid4().hex[:12]
    storage.create_analysis(job_id, stage_total=len(ANALYSIS_STAGES))
    background_tasks.add_task(_run_job, job_id, changes, product, notes)
    return {"job_id": job_id, "status_url": f"/analyses/{job_id}"}


@router.get("/analyses/{job_id}")
def job_status(job_id: str):
    job = storage.get_analysis(job_id)
    if not job:
        raise HTTPException(404, "분석 작업을 찾을 수 없습니다.")
    return job


@router.get("/analyses/{job_id}/stream")
async def job_status_stream(job_id: str):
    """SSE로 실제 backend 단계 진행 상황을 push한다. 가짜 percentage는 계산하지 않는다 —
    stage_index/stage_total은 RegressionAnalyzer._execute가 실제로 지나간 단계만 기록한다."""
    if not storage.get_analysis(job_id):
        raise HTTPException(404, "분석 작업을 찾을 수 없습니다.")

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


@router.get("/config/status")
def config_status():
    """Gemini Key 설정 여부만 반환한다. Key 값은 포함하지 않는다."""
    status = get_settings().secret_status()
    status["daily_token_usage"] = daily_token_status()
    return status


@router.post("/config/reload")
def config_reload():
    """secrets.txt/secrets.json을 수정한 뒤 재시작 없이 다시 읽는다."""
    return reload_settings().secret_status()


@router.get("/reports/{filename}")
def report(filename: str):
    safe = Path(filename).name
    path = get_settings().path("storage.report_dir") / safe
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="text/html")


@router.get("/exports/{filename}")
def export(filename: str):
    safe = Path(filename).name
    path = get_settings().path("storage.export_dir") / safe
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=safe)


@router.get("/generated_tc/{filename}")
def generated_tc(filename: str):
    safe = Path(filename).name
    path = get_settings().path("storage.generated_tc_dir") / safe
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=safe)
