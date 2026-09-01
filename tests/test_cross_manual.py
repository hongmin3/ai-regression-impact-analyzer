from docx import Document

from app.core.storage import Storage
from app.modules.manual_review.cross_manual import find_cross_manual_impacts, load_other_manual_sources
from app.modules.manual_review.release_scope import ReleaseChange


def _write_docx(path, paragraphs):
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)


def test_cross_manual_uses_latest_other_manual_and_excludes_current(tmp_path):
    storage = Storage(tmp_path / "app.db")
    service = tmp_path / "service.docx"
    operation = tmp_path / "operation.docx"
    _write_docx(service, ["서비스 점검 절차를 설명하는 충분히 긴 문장입니다."])
    _write_docx(operation, [
        "IC 카드 로그인 기능의 사용자 인증 절차를 설명합니다.",
        "환자 검색 화면의 기본 사용 방법을 설명합니다.",
        "영상 밝기 설정 방법을 설명하는 별도 문단입니다.",
        "출력 레이아웃 설정 방법을 설명하는 별도 문단입니다.",
        "배터리 상태 확인 방법을 설명하는 별도 문단입니다.",
    ])
    storage.add_manual_revision("Test Product", "Service Manual", "W1", service, status="REVIEWED")
    storage.add_manual_revision("Test Product", "Operation Manual", "W1", operation, status="REVIEWED")

    sources = load_other_manual_sources(storage, "Test Product", "Service Manual")
    impacts = find_cross_manual_impacts(
        storage, "Test Product", "Service Manual",
        [ReleaseChange("release.docx", "Added", "IC 카드 로그인 기능")],
    )

    assert [source[0] for source in sources] == ["Operation Manual"]
    assert len(impacts) == 1
    assert impacts[0].target_manual == "Operation Manual"
    assert "IC 카드" in impacts[0].evidence_text
    assert impacts[0].relevance_score > 0


def test_cross_manual_returns_empty_without_release_scope(tmp_path):
    assert find_cross_manual_impacts(Storage(tmp_path / "app.db"), "VXvue", "Service Manual", []) == []
