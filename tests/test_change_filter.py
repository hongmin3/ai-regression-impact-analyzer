from app.modules.manual_review.change_filter import is_functional_change
from app.modules.manual_review.docx_track_changes import TrackedChange


def _change(text: str) -> TrackedChange:
    return TrackedChange(kind="insertion", author="연구소", date="2026-08-01T00:00:00Z", text=text, paragraph_index=0)


def test_page_number_is_non_functional():
    assert is_functional_change(_change("12")) is False
    assert is_functional_change(_change("- 12 -")) is False


def test_copyright_notice_is_non_functional():
    assert is_functional_change(_change("Copyright 2026 Vieworks Co., Ltd.")) is False


def test_revision_label_is_non_functional():
    assert is_functional_change(_change("Rev. 1.7")) is False


def test_toc_leader_is_non_functional():
    assert is_functional_change(_change("4.2 License .......... 12")) is False


def test_empty_text_is_non_functional():
    assert is_functional_change(_change("   ")) is False


def test_real_content_change_is_functional():
    assert is_functional_change(_change("Trial License는 재발급할 수 없다.")) is True
