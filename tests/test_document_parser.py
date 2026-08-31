import zipfile

import pytest

from app.parsers.document_parser import extract_document_text, parse_document


def _write_docx(path, paragraphs: list[str]) -> None:
    body = "".join(f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def test_docx_extraction_and_chunking(tmp_path):
    path = tmp_path / "spec.docx"
    _write_docx(path, ["Display Configuration", "Brightness behavior changed"])

    assert extract_document_text(path) == "Display Configuration\nBrightness behavior changed"
    chunks = parse_document(path, "spec", chunk_chars=30)

    assert len(chunks) == 2
    assert chunks[0].heading == "Display Configuration"
    assert chunks[0].page == 1
    assert chunks[0].chunk_id == "spec-p1-0"


def test_legacy_doc_is_rejected_with_clear_message(tmp_path):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"legacy")

    with pytest.raises(ValueError, match="지원하지 않는 문서 형식"):
        extract_document_text(path)
