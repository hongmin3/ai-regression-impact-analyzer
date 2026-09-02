import sqlite3

from app.core import config
from scripts.backup_data import create_backup, verify_backup


def test_backup_round_trip_verifies_sqlite_and_manifest(monkeypatch, tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "config.yaml").write_text("storage:\n  upload_dir: data/uploads\n  specification_dir: data/specifications\n  testcase_dir: data/testcases\n  index_dir: data/indexes\n  report_dir: output/reports\n  export_dir: output/exports\n  generated_tc_dir: output/generated_tc\n  log_dir: output/logs\n  manual_revision_dir: data/manual_revisions\n  manual_review_comment_dir: output/comments\n", encoding="utf-8")
    settings = config.build_settings(root)
    monkeypatch.setattr("scripts.backup_data.get_settings", lambda: settings)
    with sqlite3.connect(root / "data" / "app.db") as db:
        db.execute("CREATE TABLE sample(value TEXT)")
        db.execute("INSERT INTO sample VALUES ('ok')")
    archive = create_backup(tmp_path / "backups")
    assert verify_backup(archive)["status"] == "ok"
