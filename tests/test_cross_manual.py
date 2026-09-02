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


def test_manual_hub_current_versions_join_the_comparison_sources(tmp_path, monkeypatch):
    """매뉴얼 서버의 Current 버전이 대조 대상에 합쳐진다.

    로컬에 리비전이 없는 매뉴얼도 조직이 최신본으로 인정한 문서로 대조할 수 있어야
    한다 — 저장소를 합친 두 시스템을 기능으로 잇는 지점이다."""
    storage = Storage(tmp_path / "app.db")
    service = tmp_path / "service.docx"
    _write_docx(service, ["서비스 점검 절차를 설명하는 충분히 긴 문장입니다."])
    storage.add_manual_revision("Test Product", "Service Manual", "W1", service, status="REVIEWED")

    hub_file = tmp_path / "hub_operation.docx"
    _write_docx(hub_file, ["매뉴얼 서버가 보관 중인 최신 Operation Manual 본문입니다."])
    monkeypatch.setattr(
        "app.modules.manual_review.cross_manual.load_manual_hub_sources",
        lambda product, current: {"Operation Manual": ("Operation Manual (매뉴얼 서버 Rev.1.3)", hub_file)},
    )

    sources = load_other_manual_sources(storage, "Test Product", "Service Manual")
    by_name = {name: label for name, label, _path in sources}
    assert "Operation Manual" in by_name
    assert "매뉴얼 서버" in by_name["Operation Manual"]
    assert "Service Manual" not in by_name  # 검증 중인 매뉴얼 자신은 제외


def test_local_revision_wins_over_manual_hub_for_the_same_manual(tmp_path, monkeypatch):
    """같은 매뉴얼이 양쪽에 있으면 이번 검증 흐름에 올라온 로컬 리비전이 이긴다."""
    storage = Storage(tmp_path / "app.db")
    local = tmp_path / "local_operation.docx"
    _write_docx(local, ["로컬에 등록된 Operation Manual 최신 리비전 본문입니다."])
    storage.add_manual_revision("Test Product", "Operation Manual", "W2", local, status="REVIEWED")

    hub_file = tmp_path / "hub_operation.docx"
    _write_docx(hub_file, ["매뉴얼 서버 사본입니다."])
    monkeypatch.setattr(
        "app.modules.manual_review.cross_manual.load_manual_hub_sources",
        lambda product, current: {"Operation Manual": ("hub", hub_file)},
    )

    sources = load_other_manual_sources(storage, "Test Product", "Service Manual")
    paths = {name: path for name, _label, path in sources}
    assert paths["Operation Manual"] == local


def test_manual_hub_outage_does_not_break_cross_manual(tmp_path, monkeypatch):
    """하위 서비스가 내려가도 매뉴얼 개정 검증은 계속된다.

    저장소만 합치고 장애는 전파되는 결합이 되면 안 된다."""
    storage = Storage(tmp_path / "app.db")
    operation = tmp_path / "operation.docx"
    _write_docx(operation, ["로컬 Operation Manual 본문입니다. 충분히 긴 문장입니다."])
    storage.add_manual_revision("Test Product", "Operation Manual", "W1", operation, status="REVIEWED")

    def explode(_product, _current):
        raise RuntimeError("매뉴얼 서버 연결 실패")

    monkeypatch.setattr("app.core.manual_hub_client.from_settings",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))

    # load_manual_hub_sources 는 내부에서 예외를 삼키고 빈 dict 를 돌려줘야 한다.
    from app.modules.manual_review.cross_manual import load_manual_hub_sources
    assert load_manual_hub_sources("Test Product", "Service Manual") == {}

    sources = load_other_manual_sources(storage, "Test Product", "Service Manual")
    assert [name for name, _label, _path in sources] == ["Operation Manual"]


def test_integration_is_skipped_when_not_configured(tmp_path):
    """자격증명이 없으면 조회 자체를 하지 않는다 (기본 상태)."""
    from app.modules.manual_review.cross_manual import load_manual_hub_sources
    assert load_manual_hub_sources("Test Product", "Service Manual") == {}
