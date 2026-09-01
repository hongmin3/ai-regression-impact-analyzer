import fitz
import pytest

from app.core.storage import Storage
from app.modules.manual_review.ai_client import ManualReviewAIClient
from app.modules.manual_review.pdf_revision_diff import extract_pdf_revision_diff
from app.modules.manual_review.reviewer import ManualRevisionReviewer


def _write_pdf(path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _mock_ai(storage: Storage) -> ManualReviewAIClient:
    def responder(prompt: str) -> dict:
        if '"stage": "quick"' in prompt:
            return {"decision": "PASS", "confidence": 0.92, "reason_codes": [], "requires_detail_generation": False}
        raise AssertionError("PASS는 상세 호출을 하지 않아야 합니다.")
    return ManualReviewAIClient(storage, responder=responder)


def test_pdf_diff_extracts_page_modification(tmp_path):
    previous = tmp_path / "previous.pdf"
    current = tmp_path / "current.pdf"
    _write_pdf(previous, ["DICOM TLS is disabled."])
    _write_pdf(current, ["DICOM TLS is enabled."])

    result = extract_pdf_revision_diff(previous, current)

    assert len(result.changes) == 1
    assert result.changes[0].kind == "pdf_modification"
    assert result.changes[0].source_page == 1
    assert result.changes[0].review_required is True


def test_first_pdf_is_registered_as_baseline_without_ai(tmp_path):
    storage = Storage(tmp_path / "app.db")
    baseline = tmp_path / "baseline.pdf"
    _write_pdf(baseline, ["Baseline manual"])

    result = ManualRevisionReviewer(ai_client=_mock_ai(storage), storage=storage).run(
        baseline, "VXvue", "Service Manual", "Baseline"
    )

    assert result["pdf_baseline"] is True
    assert result["request_count"] == 0
    assert storage.get_manual_revision(result["revision_id"])["status"] == "BASELINE"


def test_invalid_pdf_baseline_is_rejected(tmp_path):
    storage = Storage(tmp_path / "app.db")
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"%PDF-invalid")

    with pytest.raises(ValueError, match="PDF 매뉴얼을 읽을 수 없습니다"):
        ManualRevisionReviewer(ai_client=_mock_ai(storage), storage=storage).run(
            invalid, "VXvue", "Service Manual", "Baseline"
        )


def test_pdf_diff_caps_confidence_and_requires_human_review(tmp_path):
    storage = Storage(tmp_path / "app.db")
    previous = tmp_path / "previous.pdf"
    current = tmp_path / "current.pdf"
    _write_pdf(previous, ["DICOM TLS is disabled."])
    _write_pdf(current, ["DICOM TLS is enabled."])
    baseline = ManualRevisionReviewer(ai_client=_mock_ai(storage), storage=storage).run(
        previous, "VXvue", "Service Manual", "Baseline"
    )

    result = ManualRevisionReviewer(ai_client=_mock_ai(storage), storage=storage).run(
        current, "VXvue", "Service Manual", "W1", parent_revision_id=baseline["revision_id"]
    )
    change = storage.list_manual_changes(result["revision_id"])[0]

    assert change["source_page"] == 1
    assert change["review_required"] == 1
    assert change["confidence"] == 0.6
    assert change["ai_judgment"]["needs_human_review"] is True
    assert "PDF_DIFF_REVIEW_REQUIRED" in change["ai_judgment"]["reason_codes"]
