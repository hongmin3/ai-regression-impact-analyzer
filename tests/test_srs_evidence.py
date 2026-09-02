import zipfile
from types import SimpleNamespace

import pytest

from app.core import document_cache
from app.core.storage import Storage
from app.modules.manual_review.srs_evidence import load_srs_chunks, search_candidates


@pytest.fixture(autouse=True)
def isolated_document_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "indexes"
    monkeypatch.setattr(document_cache, "get_settings", lambda: SimpleNamespace(path=lambda dotted: cache_dir))


def _write_docx(path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def test_load_srs_chunks_reads_registered_specifications(tmp_path):
    storage = Storage(tmp_path / "app.db")
    spec_path = tmp_path / "srs.docx"
    _write_docx(spec_path, ["Trial License 발급 조건", "동일 제품의 정식 License 이력이 있으면 재발급할 수 없다."])
    storage.add_document("specification", "VXvue", "1.0", "", "VXvue SRS.docx", spec_path)

    chunks, doc_labels = load_srs_chunks(storage, "VXvue")

    # DOCX는 parse_document의 char-offset 분할기를 쓰므로(페이지 개념 없음), 두 문단이
    # 1800자 미만이면 하나의 chunk로 합쳐진다 — 문단마다 별도 chunk가 되는 PDF와 다르다.
    assert len(chunks) == 1
    assert "Trial License 발급 조건" in chunks[0].text
    assert "재발급할 수 없다" in chunks[0].text
    assert doc_labels[spec_path.stem] == "VXvue SRS.docx"


def test_load_srs_chunks_skips_missing_files(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.add_document("specification", "VXvue", "1.0", "", "missing.pdf", tmp_path / "missing.pdf")

    chunks, doc_labels = load_srs_chunks(storage, "VXvue")

    assert chunks == []
    assert doc_labels == {}


def test_load_srs_chunks_reuses_cached_parse(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    spec_path = tmp_path / "srs.docx"
    _write_docx(spec_path, ["캐시되는 SRS"])
    document_id = storage.add_document("specification", "VXvue", "1.0", "", "SRS.docx", spec_path)

    first_chunks, _ = load_srs_chunks(storage, "VXvue")
    assert document_cache.load(document_id, type(first_chunks[0])) == first_chunks
    monkeypatch.setattr("app.modules.manual_review.srs_evidence.parse_document", lambda *args: (_ for _ in ()).throw(AssertionError("reparsed")))

    second_chunks, _ = load_srs_chunks(storage, "VXvue")

    assert second_chunks == first_chunks


def test_search_candidates_ranks_relevant_chunk_first(tmp_path):
    storage = Storage(tmp_path / "app.db")
    spec_path = tmp_path / "srs.docx"
    _write_docx(spec_path, ["Trial License는 재발급할 수 없다.", "Display 밝기 설정은 자동 저장된다."])
    storage.add_document("specification", "VXvue", "1.0", "", "SRS.docx", spec_path)
    chunks, _ = load_srs_chunks(storage, "VXvue")

    results = search_candidates(chunks, "Trial License 재발급 제한", top_k=1)

    assert len(results) == 1
    assert "Trial License" in results[0].text


def test_search_candidates_empty_query_returns_empty():
    assert search_candidates([], "", top_k=6) == []
