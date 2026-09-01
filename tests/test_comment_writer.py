import zipfile

from docx import Document

from app.modules.manual_review.comment_writer import comment_text_for, insert_comments, output_filename

W_NS_DECL = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
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


def _write_minimal_docx(path, body: str) -> None:
    xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS_DECL}><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)


def test_output_filename_matches_spec_convention():
    assert output_filename("VXvue Service Manual", "V1.1.0 W2") == "VXvue Service Manual.V1.1.0W2_KO_AI검토.docx"


def test_output_filename_sanitizes_unsafe_characters():
    assert "/" not in output_filename("A/B", "W1")


def test_comment_text_for_pass_returns_none():
    assert comment_text_for({"decision": "PASS"}) is None


def test_comment_text_for_none_decision_returns_none():
    assert comment_text_for({"decision": None}) is None


def test_comment_text_for_uses_ai_qa_comment():
    change = {"decision": "SUPPLEMENT_REQUIRED", "ai_judgment": {"qa_comment": "조건이 누락되었습니다."}}
    assert comment_text_for(change) == "조건이 누락되었습니다."


def test_comment_text_for_appends_qa_note():
    change = {"decision": "MODIFICATION_REQUIRED", "ai_judgment": {"qa_comment": "문제"}, "qa_note": "재확인 요망"}
    assert comment_text_for(change) == "문제 (QA 메모: 재확인 요망)"


def test_comment_text_for_qa_override_to_pass_suppresses_comment():
    change = {"decision": "SUPPLEMENT_REQUIRED", "qa_decision": "PASS"}
    assert comment_text_for(change) is None


def test_comment_text_for_falls_back_when_no_qa_comment():
    change = {"decision": "MISSING_SUSPECTED"}
    assert comment_text_for(change) == "[MISSING_SUSPECTED] 검토가 필요합니다."


def test_insert_comments_anchors_to_tracked_change_paragraph(tmp_path):
    body = (
        '<w:p><w:ins w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t>Trial License는 재발급할 수 있다.</w:t></w:r></w:ins></w:p>"
        "<w:p><w:r><w:t>변경 없는 문단.</w:t></w:r></w:p>"
    )
    revision_path = tmp_path / "revision.docx"
    _write_minimal_docx(revision_path, body)
    changes = [{"paragraph_index": 0, "functional": True, "decision": "MODIFICATION_REQUIRED", "ai_judgment": {"qa_comment": "SRS와 다릅니다."}}]
    output_path = tmp_path / "out.docx"

    inserted = insert_comments(revision_path, changes, output_path)

    assert inserted == 1
    assert output_path.exists()
    result_doc = Document(str(output_path))
    comments = list(result_doc.comments)
    assert len(comments) == 1
    assert comments[0].author == "QA AI"
    assert comments[0].text == "SRS와 다릅니다."


def test_insert_comments_skips_pass_and_non_functional(tmp_path):
    body = "<w:p><w:r><w:t>변경 없음.</w:t></w:r></w:p>"
    revision_path = tmp_path / "revision.docx"
    _write_minimal_docx(revision_path, body)
    changes = [
        {"paragraph_index": 0, "functional": True, "decision": "PASS"},
        {"paragraph_index": 0, "functional": False, "decision": "MODIFICATION_REQUIRED"},
    ]
    output_path = tmp_path / "out.docx"

    inserted = insert_comments(revision_path, changes, output_path)

    assert inserted == 0


def test_insert_comments_skips_out_of_range_paragraph_index(tmp_path):
    body = "<w:p><w:r><w:t>단일 문단.</w:t></w:r></w:p>"
    revision_path = tmp_path / "revision.docx"
    _write_minimal_docx(revision_path, body)
    changes = [{"paragraph_index": 5, "functional": True, "decision": "SUPPLEMENT_REQUIRED"}]
    output_path = tmp_path / "out.docx"

    inserted = insert_comments(revision_path, changes, output_path)

    assert inserted == 0
