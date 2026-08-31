from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.analyzers.regression_analyzer import RegressionAnalyzer
from app.core.config import get_settings
from app.core.storage import Storage
from app.parsers.pdf_parser import parse_specification

router = APIRouter()
templates = Jinja2Templates(directory=str(get_settings().root / "app" / "web" / "templates"))
storage = Storage()
jobs: dict[str, dict] = {}


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
    return templates.TemplateResponse(request, "index.html", {"specs": storage.list_documents("specification"), "testcases": storage.list_documents("testcase")})


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request):
    return templates.TemplateResponse(request, "knowledge.html", {"specs": storage.list_documents("specification"), "testcases": storage.list_documents("testcase")})


@router.post("/knowledge/specification")
def register_specification(file: UploadFile = File(...), product: str = Form(...), version: str = Form(""), revision: str = Form("")):
    settings = get_settings()
    path = _save_upload(file, settings.path("storage.specification_dir"), {".pdf"})
    chunks = parse_specification(path, path.stem)
    storage.add_document("specification", product, version, revision, file.filename or path.name, path, {"chunk_count": len(chunks)})
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/testcase")
def register_testcase(file: UploadFile = File(...), product: str = Form(...), version: str = Form(""), revision: str = Form("")):
    path = _save_upload(file, get_settings().path("storage.testcase_dir"), {".xlsx"})
    storage.add_document("testcase", product, version, revision, file.filename or path.name, path)
    return RedirectResponse("/knowledge", status_code=303)


def _run_job(job_id: str, change: Path, specification: Path, testcase: Path) -> None:
    try:
        jobs[job_id] = {"status": "RUNNING"}
        result = RegressionAnalyzer().run(change, specification, testcase)
        jobs[job_id] = {"status": "DONE", "result": result.model_dump(mode="json")}
    except Exception as exc:
        jobs[job_id] = {"status": "FAILED", "error": str(exc)}


@router.post("/analyses")
def start_analysis(background_tasks: BackgroundTasks, change_file: UploadFile = File(...), specification_id: int = Form(...), testcase_id: int = Form(...)):
    specification = storage.get_document(specification_id)
    testcase = storage.get_document(testcase_id)
    if not specification or not testcase:
        raise HTTPException(404, "선택한 사양서 또는 TC를 찾을 수 없습니다.")
    change = _save_upload(change_file, get_settings().path("storage.upload_dir"), {".pdf"})
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"status": "QUEUED"}
    background_tasks.add_task(_run_job, job_id, change, Path(specification["path"]), Path(testcase["path"]))
    return {"job_id": job_id, "status_url": f"/analyses/{job_id}"}


@router.get("/analyses/{job_id}")
def job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "분석 작업을 찾을 수 없습니다.")
    return jobs[job_id]


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
