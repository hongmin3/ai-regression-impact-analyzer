from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.storage import Storage
from app.core.uploads import save_upload
from app.parsers.document_parser import parse_document

router = APIRouter()
templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", get_settings().root / "app" / "web" / "templates"])
storage = Storage()


@router.post("/knowledge/products")
def register_product(product: str = Form(...)):
    product = product.strip()
    if not product:
        raise HTTPException(400, "제품명을 입력하세요.")
    storage.ensure_product(product)
    return RedirectResponse("/knowledge", status_code=303)


def _versions_by_product() -> dict[str, list[str]]:
    return {product: storage.list_versions(product) for product in storage.list_products()}


def _grouped_by_product_version(kind: str) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for document in storage.list_documents(kind):
        groups.setdefault((document["product"], document["version"]), []).append(document)
    return [{"product": product, "version": version, "documents": documents} for (product, version), documents in groups.items()]


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


@router.post("/knowledge/specification")
def register_specification(file: UploadFile = File(...), product: str = Form(...), version: str = Form("")):
    settings = get_settings()
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    path = save_upload(file, settings.path("storage.specification_dir"), {".pdf", ".docx"})
    chunks = parse_document(path, path.stem)
    storage.add_document("specification", product, version, "", file.filename or path.name, path, {"chunk_count": len(chunks)})
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/testcase")
def register_testcase(file: UploadFile = File(...), product: str = Form(...), version: str = Form("")):
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    path = save_upload(file, get_settings().path("storage.testcase_dir"), {".xlsx"})
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
    return [{"id": doc["id"], "name": doc["name"]} for doc in storage.active_documents(kind, product)]


@router.post("/knowledge/sync-log")
def record_sync_log(product: str = Form(...), kind: str = Form(...), source: str = Form(...), status: str = Form(...), detail: str = Form("")):
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
