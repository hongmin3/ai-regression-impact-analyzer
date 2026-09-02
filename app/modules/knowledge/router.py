from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import document_cache
from app.core.config import get_settings
from app.core.storage import Storage
from app.core.uploads import save_upload
from app.parsers.document_parser import extract_document_text, parse_document
from app.parsers.excel_parser import parse_testcases, preview_workbook, suggest_columns

router = APIRouter()
templates = Jinja2Templates(directory=[Path(__file__).parent / "templates", get_settings().root / "app" / "web" / "templates"])
storage = Storage()

TC_FIELD_LABELS = {
    "tc_id": "TC ID (필수)", "category": "분류", "feature": "기능명", "precondition": "사전조건",
    "step": "시험절차", "expected_result": "예상결과", "result": "결과", "remark": "비고",
}


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
    document_id = storage.add_document("specification", product, version, "", file.filename or path.name, path, {"chunk_count": len(chunks)})
    # 분석/매뉴얼 검증이 매번 원본을 다시 파싱하지 않도록 지금 파싱한 결과를 바로 캐시해둔다
    # (Rule 기반 diff가 쓰는 전체 원문도 함께 — 둘 다 원본 파일을 다시 여는 비용이 크다).
    document_cache.save(document_id, chunks)
    document_cache.save_text(document_id, extract_document_text(path))
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/testcase")
def register_testcase(file: UploadFile = File(...), product: str = Form(...), version: str = Form("")):
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    path = save_upload(file, get_settings().path("storage.testcase_dir"), {".xlsx"})
    original_name = file.filename or path.name
    try:
        cases = parse_testcases(path)
    except ValueError:
        # 자동 탐지 실패 — 파일은 이미 storage.testcase_dir에 저장돼 있으니 삭제하지 않고
        # 수동 매핑 화면으로 보낸다. 사용자가 매핑을 확정해야 documents 테이블에 등록된다.
        params = urlencode({"filename": path.name, "product": product, "version": version, "original_name": original_name})
        return RedirectResponse(f"/knowledge/testcase/map?{params}", status_code=303)
    document_id = storage.add_document("testcase", product, version, "", original_name, path)
    document_cache.save(document_id, cases)
    return RedirectResponse("/knowledge", status_code=303)


def _testcase_upload_path(filename: str) -> Path:
    if filename != Path(filename).name:
        raise HTTPException(400, "잘못된 파일명입니다.")
    path = get_settings().path("storage.testcase_dir") / filename
    if not path.exists():
        raise HTTPException(404, "업로드된 파일을 찾을 수 없습니다. TC 파일을 다시 첨부하세요.")
    return path


@router.get("/knowledge/testcase/map", response_class=HTMLResponse)
def testcase_mapping_form(
    request: Request, filename: str, product: str, version: str = "", original_name: str = "",
    sheet: str = "", header_row: int = 0, error: str = "",
):
    """`register_testcase`가 TC ID 컬럼을 자동으로 못 찾았을 때 QA가 시트/헤더 행/컬럼을
    직접 지정하는 화면. 시트 선택·헤더 행 입력까지는 GET으로 미리보기만 갱신하고, 실제
    등록은 아래 POST에서 확정한다."""
    path = _testcase_upload_path(filename)
    preview = preview_workbook(path)
    sheet_names = list(preview.keys())
    selected_sheet = sheet if sheet in preview else (sheet_names[0] if sheet_names else "")
    preview_rows = preview.get(selected_sheet, [])
    suggested: dict[str, str] = {}
    if header_row and 1 <= header_row <= len(preview_rows):
        header_cells = preview_rows[header_row - 1]
        suggested = {field: header_cells[index] for index, field in suggest_columns(header_cells).items() if header_cells[index]}
    return templates.TemplateResponse(
        request,
        "testcase_mapping.html",
        {
            "filename": filename, "product": product, "version": version, "original_name": original_name,
            "sheets": sheet_names, "selected_sheet": selected_sheet, "preview_rows": preview_rows,
            "header_row": header_row, "fields": TC_FIELD_LABELS, "suggested": suggested, "error": error,
        },
    )


@router.post("/knowledge/testcase/map")
def register_testcase_with_mapping(
    filename: str = Form(...), product: str = Form(...), version: str = Form(""), original_name: str = Form(""),
    sheet: str = Form(...), header_row: int = Form(...),
    tc_id: str = Form(""), category: str = Form(""), feature: str = Form(""), precondition: str = Form(""),
    step: str = Form(""), expected_result: str = Form(""), result: str = Form(""), remark: str = Form(""),
):
    path = _testcase_upload_path(filename)
    mapping = {
        key: value for key, value in {
            "tc_id": tc_id, "category": category, "feature": feature, "precondition": precondition,
            "step": step, "expected_result": expected_result, "result": result, "remark": remark,
        }.items() if value
    }
    try:
        cases = parse_testcases(path, mapping=mapping, sheet_name=sheet, header_row=header_row)
    except ValueError as exc:
        params = urlencode({
            "filename": filename, "product": product, "version": version, "original_name": original_name,
            "sheet": sheet, "header_row": header_row, "error": str(exc),
        })
        return RedirectResponse(f"/knowledge/testcase/map?{params}", status_code=303)
    storage.ensure_product(product)
    storage.ensure_version(product, version)
    document_id = storage.add_document("testcase", product, version, "", original_name or filename, path)
    storage.update_document_metadata(document_id, {"column_mapping": mapping, "sheet_name": sheet, "header_row": header_row})
    document_cache.save(document_id, cases)
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/delete/{document_id}")
def delete_document(document_id: int):
    document = storage.get_document(document_id)
    if not document:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    storage.delete_document(document_id)
    document_cache.delete(document_id)
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
