import zipfile

from docx import Document
from fastapi.testclient import TestClient

import app.modules.manual_review.router as manual_review_router
from app.core.storage import Storage
from app.main import app

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def _write_minimal_docx(path) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>변경 없음.</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)


def test_home_renders_empty_state(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)

    response = TestClient(app).get("/manual-review")

    assert response.status_code == 200
    assert "아직 등록된 검증 이력이 없습니다." in response.text


def test_upload_rejects_non_docx(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)

    response = TestClient(app).post(
        "/manual-review/revisions",
        files={"file": ("change.pdf", b"%PDF-", "application/pdf")},
        data={"product": "VXvue", "manual_name": "Service Manual", "revision_label": "W1"},
    )

    assert response.status_code == 400


def test_view_missing_revision_returns_404(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)

    response = TestClient(app).get("/manual-review/revisions/999/view")

    assert response.status_code == 404


def test_view_renders_change_and_ai_judgment(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "2026-08-01", 0, "Trial License는 재발급할 수 있다.", functional=True)
    storage.update_manual_change_judgment(
        change_id, "MODIFICATION_REQUIRED", 0.7,
        {"decision": "MODIFICATION_REQUIRED", "confidence": 0.7, "reason_codes": [], "problem": "삭제 사양 재사용", "recommended_manual_text": "", "qa_comment": "QA 코멘트 초안", "evidence": [], "needs_human_review": False, "prompt_version": 1},
    )

    response = TestClient(app).get(f"/manual-review/revisions/{revision_id}/view")

    assert response.status_code == 200
    assert "삭제 사양 재사용" in response.text
    assert "QA 코멘트 초안" in response.text
    assert "수정 필요" in response.text  # MODIFICATION_REQUIRED의 한국어 표시


def test_view_renders_missing_suspected_release_findings(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    storage.add_release_finding(revision_id, "release_note", "Added", "매뉴얼에 반영 안 된 기능", status="MISSING_SUSPECTED")
    storage.add_release_finding(revision_id, "release_note", "Added", "정상 반영된 기능", status="FOUND", matched_change_id=1)

    response = TestClient(app).get(f"/manual-review/revisions/{revision_id}/view")

    assert response.status_code == 200
    assert "매뉴얼에 반영 안 된 기능" in response.text
    assert "정상 반영된 기능" not in response.text  # FOUND 항목은 누락 의심 섹션에 표시하지 않음


def test_qa_decision_override_persists(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "2026-08-01", 0, "문구", functional=True)
    storage.update_manual_change_judgment(change_id, "SUPPLEMENT_REQUIRED", 0.6, {"decision": "SUPPLEMENT_REQUIRED", "confidence": 0.6})

    response = TestClient(app).post(
        f"/manual-review/revisions/{revision_id}/changes/{change_id}/qa-decision",
        data={"qa_decision": "PASS", "qa_note": "QA가 직접 확인함"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    change = storage.get_manual_change(change_id)
    assert change["qa_decision"] == "PASS"
    assert change["qa_note"] == "QA가 직접 확인함"


def test_comment_docx_download_returns_400_when_nothing_to_flag(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_path = tmp_path / "r.docx"
    _write_minimal_docx(revision_path)
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", revision_path)
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "", 0, "문구", functional=True)
    storage.update_manual_change_judgment(change_id, "PASS", 0.9, {"decision": "PASS"})

    response = TestClient(app).get(f"/manual-review/revisions/{revision_id}/comment-docx")

    assert response.status_code == 400


def test_comment_docx_download_uses_product_specific_author(monkeypatch, tmp_path):
    """제품명이 코드에 고정되어 있지 않고 revision.product로부터 조립되는지 확인 —
    다른 제품(예: Bellalun Viewer)으로도 그대로 재사용 가능해야 한다."""
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_path = tmp_path / "r.docx"
    _write_minimal_docx(revision_path)
    revision_id = storage.add_manual_revision("Bellalun Viewer", "Operation Manual", "W1", revision_path)
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "", 0, "문구", functional=True)
    storage.update_manual_change_judgment(change_id, "SUPPLEMENT_REQUIRED", 0.6, {"decision": "SUPPLEMENT_REQUIRED", "qa_comment": "조건 추가 필요"})

    response = TestClient(app).get(f"/manual-review/revisions/{revision_id}/comment-docx")

    assert response.status_code == 200
    saved_path = tmp_path / "downloaded.docx"
    saved_path.write_bytes(response.content)
    comments = list(Document(str(saved_path)).comments)
    assert len(comments) == 1
    assert comments[0].author == "Bellalun Viewer QA AI"


def test_comment_docx_download_missing_revision_returns_404(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)

    response = TestClient(app).get("/manual-review/revisions/999/comment-docx")

    assert response.status_code == 404


def test_qa_decision_for_wrong_revision_returns_404(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(manual_review_router, "storage", storage)
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "2026-08-01", 0, "문구", functional=True)

    response = TestClient(app).post(
        f"/manual-review/revisions/999999/changes/{change_id}/qa-decision",
        data={"qa_decision": "PASS"},
        follow_redirects=False,
    )

    assert response.status_code == 404
