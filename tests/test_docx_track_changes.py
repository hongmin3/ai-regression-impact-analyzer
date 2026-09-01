import zipfile

from app.modules.manual_review.docx_track_changes import extract_track_changes, extract_track_changes_from_xml

W_NS_DECL = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _document_xml(body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W_NS_DECL}><w:body>{body}</w:body></w:document>"
    ).encode("utf-8")


def test_extracts_insertion_and_deletion():
    body = (
        "<w:p>"
        '<w:ins w:id="1" w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t>신규 문구를 추가한다.</w:t></w:r></w:ins>"
        '<w:del w:id="2" w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:delText>기존 문구를 삭제한다.</w:delText></w:r></w:del>"
        "</w:p>"
    )
    result = extract_track_changes_from_xml(_document_xml(body))

    assert [c.kind for c in result.changes] == ["insertion", "deletion"]
    assert result.changes[0].text == "신규 문구를 추가한다."
    assert result.changes[0].author == "연구소"
    assert result.changes[1].text == "기존 문구를 삭제한다."
    assert result.plain_text == "신규 문구를 추가한다."


def test_extracts_move_from_and_move_to():
    body = (
        '<w:p><w:moveFrom w:id="1" w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t>이동되는 문단</w:t></w:r></w:moveFrom></w:p>"
        '<w:p><w:moveTo w:id="2" w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t>이동되는 문단</w:t></w:r></w:moveTo></w:p>"
    )
    result = extract_track_changes_from_xml(_document_xml(body))

    assert [c.kind for c in result.changes] == ["move_from", "move_to"]
    assert result.plain_text == "이동되는 문단"


def test_plain_text_keeps_unchanged_runs_alongside_tracked_changes():
    body = (
        "<w:p><w:r><w:t>변경되지 않은 문장.</w:t></w:r>"
        '<w:ins w:author="연구소" w:date="2026-08-01T00:00:00Z">'
        "<w:r><w:t> 추가된 문장.</w:t></w:r></w:ins></w:p>"
    )
    result = extract_track_changes_from_xml(_document_xml(body))

    assert result.plain_text == "변경되지 않은 문장. 추가된 문장."


def test_extract_track_changes_reads_real_docx_zip(tmp_path):
    path = tmp_path / "revised.docx"
    body = '<w:p><w:ins w:author="연구소" w:date="2026-08-01T00:00:00Z"><w:r><w:t>추가</w:t></w:r></w:ins></w:p>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", _document_xml(body).decode("utf-8"))

    result = extract_track_changes(path)

    assert result.changes[0].kind == "insertion"
    assert result.plain_text == "추가"
