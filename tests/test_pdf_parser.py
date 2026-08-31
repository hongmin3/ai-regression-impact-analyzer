import fitz

from app.parsers.pdf_parser import extract_pdf_text, parse_specification


def test_pdf_parsing(tmp_path):
    path = tmp_path / "spec.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Display Configuration\nSetting is saved.")
    document.save(path)
    assert "Display Configuration" in extract_pdf_text(path)
    chunks = parse_specification(path, "spec")
    assert chunks[0].page == 1
    assert chunks[0].chunk_id.startswith("spec-p1")
