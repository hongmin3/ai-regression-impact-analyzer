import zipfile

from app.core.storage import Storage
from app.modules.manual_review.ai_client import ManualReviewAIClient
from app.modules.manual_review.reviewer import ManualRevisionReviewer

W_NS_DECL = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _write_revision_docx(path) -> None:
    body = (
        "<w:p>"
        '<w:ins w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t>Trial License는 정식 License 이력이 있어도 재발급할 수 있다.</w:t></w:r></w:ins>"
        "</w:p>"
        "<w:p>"
        '<w:del w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:delText>12</w:delText></w:r></w:del>"
        "</w:p>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W_NS_DECL}><w:body>{body}</w:body></w:document>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def _write_plain_docx(path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W_NS_DECL}><w:body>{body}</w:body></w:document>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def _write_multi_change_docx(path, texts: list[str]) -> None:
    body = "".join(
        f'<w:p><w:ins w:author="연구소" w:date="2026-08-01T00:00:00Z"><w:r><w:t>{text}</w:t></w:r></w:ins></w:p>' for text in texts
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W_NS_DECL}><w:body>{body}</w:body></w:document>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def _mock_ai_client(storage) -> ManualReviewAIClient:
    def responder(prompt: str) -> dict:
        if '"stage": "quick"' in prompt:
            return {"decision": "MODIFICATION_REQUIRED", "confidence": 0.65, "reason_codes": ["SPEC_MISMATCH"], "requires_detail_generation": True}
        return {"problem": "삭제된 사양을 신규 내용처럼 사용함", "recommended_manual_text": "...", "qa_comment": "SRS와 다릅니다.", "evidence": [], "needs_human_review": False}

    return ManualReviewAIClient(storage, responder=responder)


def test_reviewer_persists_functional_and_non_functional_changes(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_path = tmp_path / "revised.docx"
    _write_revision_docx(revision_path)

    reviewer = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage)
    result = reviewer.run(revision_path, "VXvue", "Service Manual", "V1.1.0 W1")

    assert result["total_changes"] == 2
    assert result["functional_changes"] == 1  # "12"는 페이지 번호로 NON_FUNCTIONAL 처리
    assert result["decision_counts"] == {"MODIFICATION_REQUIRED": 1}
    assert result["request_count"] == 2  # quick + detail (1개 functional change)

    changes = storage.list_manual_changes(result["revision_id"])
    assert len(changes) == 2
    functional = [c for c in changes if c["functional"]]
    non_functional = [c for c in changes if not c["functional"]]
    assert len(functional) == 1
    assert functional[0]["decision"] == "MODIFICATION_REQUIRED"
    assert functional[0]["ai_judgment"]["qa_comment"] == "SRS와 다릅니다."
    assert len(non_functional) == 1
    assert non_functional[0]["decision"] is None

    revision = storage.get_manual_revision(result["revision_id"])
    assert revision["status"] == "REVIEWED"
    assert revision["round_number"] == 0
    assert revision["parent_revision_id"] is None


def test_reviewer_links_round_lineage_to_parent(tmp_path):
    storage = Storage(tmp_path / "app.db")
    baseline_path = tmp_path / "baseline.docx"
    _write_revision_docx(baseline_path)
    round1 = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage).run(baseline_path, "VXvue", "Service Manual", "Baseline")

    round2_path = tmp_path / "round2.docx"
    _write_revision_docx(round2_path)
    round2 = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage).run(
        round2_path, "VXvue", "Service Manual", "W2", parent_revision_id=round1["revision_id"]
    )

    revision = storage.get_manual_revision(round2["revision_id"])
    assert revision["round_number"] == 1
    assert revision["parent_revision_id"] == round1["revision_id"]
    assert revision["baseline_revision_id"] == round1["revision_id"]


def test_reviewer_flags_release_note_item_not_reflected_in_manual(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_path = tmp_path / "revised.docx"
    _write_multi_change_docx(
        revision_path,
        [
            "IC 카드를 이용한 VXvue 로그인 기능을 추가하였다.",
            "Display 밝기 설정 자동 저장 방식을 변경하였다.",
            "프린터 상하단 레이아웃 크기를 사용자가 설정할 수 있도록 개선하였다.",
        ],
    )
    release_note_path = tmp_path / "release_note.docx"
    _write_plain_docx(release_note_path, ["Added", "IC 카드 로그인 기능", "완전히 관련 없는 신규 하드웨어 스캐너 연동"])

    reviewer = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage)
    result = reviewer.run(revision_path, "VXvue", "Service Manual", "W1", release_note_path=release_note_path)

    assert result["release_scope_total"] == 2
    assert result["release_scope_missing_suspected"] == 1

    findings = storage.list_release_findings(result["revision_id"])
    by_title = {f["title"]: f for f in findings}
    assert by_title["IC 카드 로그인 기능"]["status"] == "FOUND"
    assert by_title["완전히 관련 없는 신규 하드웨어 스캐너 연동"]["status"] == "MISSING_SUSPECTED"


def test_reviewer_skips_release_scope_when_no_reference_docs_given(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_path = tmp_path / "revised.docx"
    _write_revision_docx(revision_path)

    result = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage).run(revision_path, "VXvue", "Service Manual", "W1")

    assert result["release_scope_total"] == 0
    assert result["release_scope_missing_suspected"] == 0
    assert storage.list_release_findings(result["revision_id"]) == []


def test_design_review_fail_forces_human_review_signal(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_path = tmp_path / "revised.docx"
    _write_multi_change_docx(revision_path, [
        "IC 카드를 이용한 로그인 기능을 추가한다.", "Display 밝기 설정을 변경한다.",
        "프린터 레이아웃을 개선한다.", "배터리 상태를 표시한다.", "검색 필터를 추가한다.",
    ])
    design_path = tmp_path / "design.docx"
    _write_plain_docx(design_path, [
        "2. 문제 분석", "2.2.1 IC 카드 로그인 기능", "문제 설명",
        "4. 설계변경 적용 결과 분석", "IC 카드 로그인 기능", "Fail",
    ])

    result = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage).run(
        revision_path, "VXvue", "Service Manual", "W1", design_review_path=design_path
    )
    matched = next(change for change in storage.list_manual_changes(result["revision_id"]) if "IC 카드" in change["text"])

    assert matched["ai_judgment"]["needs_human_review"] is True
    assert "DESIGN_REVIEW_FAILED" in matched["ai_judgment"]["reason_codes"]


def test_reviewer_records_stage_progress_when_analysis_id_given(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("job-1", stage_total=5)
    revision_path = tmp_path / "revised.docx"
    _write_revision_docx(revision_path)

    ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage).run(
        revision_path, "VXvue", "Service Manual", "W1", analysis_id="job-1"
    )

    job = storage.get_analysis("job-1")
    assert job["stage_index"] == 5
    assert job["stage"] == "결과 저장"
