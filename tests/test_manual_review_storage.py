from app.core.storage import Storage


def test_add_and_get_manual_revision(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "V1.1.0 W1", tmp_path / "r.docx")

    revision = storage.get_manual_revision(revision_id)

    assert revision["product"] == "VXvue"
    assert revision["status"] == "REGISTERED"
    assert revision["round_number"] == 0
    assert revision["parent_revision_id"] is None


def test_list_manual_revisions_orders_newest_first(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "a.docx")
    storage.add_manual_revision("VXvue", "Service Manual", "W2", tmp_path / "b.docx")

    revisions = storage.list_manual_revisions("VXvue")

    assert [r["revision_label"] for r in revisions] == ["W2", "W1"]


def test_manual_change_judgment_round_trip(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "2026-08-01", 0, "문구", functional=True)

    storage.update_manual_change_judgment(change_id, "PASS", 0.95, {"decision": "PASS", "confidence": 0.95})
    change = storage.get_manual_change(change_id)

    assert change["decision"] == "PASS"
    assert change["confidence"] == 0.95
    assert change["ai_judgment"]["decision"] == "PASS"


def test_manual_change_qa_decision_override(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "insertion", "연구소", "2026-08-01", 0, "문구", functional=True)

    storage.update_manual_change_qa_decision(change_id, "PASS", "QA 직접 확인")
    change = storage.get_manual_change(change_id)

    assert change["qa_decision"] == "PASS"
    assert change["qa_note"] == "QA 직접 확인"


def test_list_manual_changes_ordered_by_paragraph_index(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    storage.add_manual_change(revision_id, "insertion", "a", "", 3, "세번째", functional=True)
    storage.add_manual_change(revision_id, "insertion", "a", "", 1, "첫번째", functional=True)

    changes = storage.list_manual_changes(revision_id)

    assert [c["text"] for c in changes] == ["첫번째", "세번째"]


def test_open_comments_carry_forward_to_next_round(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "deletion", "연구소", "", 0, "삭제된 조건 설명", functional=True)
    storage.add_manual_comment(change_id, round_number=1, comment_text="조건을 다시 추가해야 합니다.")

    open_comments = storage.list_open_comments_for_revision(revision_id)

    assert len(open_comments) == 1
    assert open_comments[0]["comment_text"] == "조건을 다시 추가해야 합니다."
    assert open_comments[0]["change_text"] == "삭제된 조건 설명"


def test_comment_status_update_removes_it_from_open_list(tmp_path):
    storage = Storage(tmp_path / "app.db")
    revision_id = storage.add_manual_revision("VXvue", "Service Manual", "W1", tmp_path / "r.docx")
    change_id = storage.add_manual_change(revision_id, "deletion", "연구소", "", 0, "삭제된 조건", functional=True)
    comment_id = storage.add_manual_comment(change_id, round_number=1, comment_text="반영 필요")

    storage.update_manual_comment_status(comment_id, "RESOLVED", resolved_in_revision_id=revision_id)

    assert storage.list_open_comments_for_revision(revision_id) == []
