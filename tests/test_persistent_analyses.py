from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.core.storage import Storage
from app.modules.impact_analyzer import router as routes
from app.modules.impact_analyzer.schemas import AnalysisResult, ChangeAnalysis


def _result(analysis_id: str) -> dict:
    return AnalysisResult(
        analysis_id=analysis_id,
        created_at=datetime.now(timezone.utc),
        change_file="change.docx",
        specification_file="spec.pdf",
        testcase_file="tc.xlsx",
        change=ChangeAnalysis(changed_features=["Display"]),
        total_tc=10,
        candidate_tc=2,
        decisions=[],
    ).model_dump(mode="json")


def test_completed_analysis_survives_storage_recreation(tmp_path):
    db_path = tmp_path / "app.db"
    first = Storage(db_path)
    first.create_analysis("job-1")
    first.update_analysis("job-1", "DONE", result=_result("job-1"))

    restored = Storage(db_path).get_analysis("job-1")

    assert restored is not None
    assert restored["status"] == "DONE"
    assert restored["result"]["analysis_id"] == "job-1"
    assert restored["result"]["change_file"] == "change.docx"


def test_incomplete_analyses_are_failed_after_restart(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("queued")
    storage.create_analysis("running", status="RUNNING")
    storage.create_analysis("done")
    storage.update_analysis("done", "DONE", result=_result("done"))

    assert storage.fail_incomplete_analyses() == 2
    assert storage.get_analysis("queued")["status"] == "FAILED"
    assert storage.get_analysis("running")["error"] == "서버 재시작으로 분석이 중단되었습니다."
    assert storage.get_analysis("done")["status"] == "DONE"


def test_job_status_reads_persisted_analysis(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    persisted.create_analysis("restored")
    persisted.update_analysis("restored", "DONE", result=_result("restored"))
    monkeypatch.setattr(routes, "storage", persisted)

    response = TestClient(app).get("/analyses/restored")

    assert response.status_code == 200
    assert response.json()["result"]["analysis_id"] == "restored"


def test_create_analysis_initializes_stage_tracking(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("job-stage", stage_total=8)

    job = storage.get_analysis("job-stage")

    assert job["stage"] == "대기 중"
    assert job["stage_index"] == 0
    assert job["stage_total"] == 8
    assert job["started_at"]


def test_update_stage_advances_progress(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("job-stage-2", stage_total=8)

    storage.update_stage("job-stage-2", 3, "TC 후보 검색", 8)
    job = storage.get_analysis("job-stage-2")

    assert job["stage"] == "TC 후보 검색"
    assert job["stage_index"] == 3


def test_sync_log_tracks_running_and_finish(tmp_path):
    storage = Storage(tmp_path / "app.db")
    assert storage.is_sync_running("VXvue", "specification") is False

    sync_id = storage.sync_start("VXvue", "specification", "alm_crawler")
    assert storage.is_sync_running("VXvue", "specification") is True

    storage.sync_finish(sync_id, "SUCCESS", "3 files updated")
    assert storage.is_sync_running("VXvue", "specification") is False
    latest = storage.latest_sync("VXvue", "specification")
    assert latest["status"] == "SUCCESS"
    assert latest["detail"] == "3 files updated"


def test_active_documents_keeps_multiple_distinct_documents(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.add_document("specification", "VXvue", "1.0", "Rev.1", "사양서1.pdf", tmp_path / "s1.pdf")
    storage.add_document("specification", "VXvue", "1.0", "Rev.2", "사양서2.pdf", tmp_path / "s2.pdf")
    storage.add_document("specification", "VXvue", "1.0", "Rev.3", "사양서3.pdf", tmp_path / "s3.pdf")

    docs = storage.active_documents("specification", "VXvue")

    assert {d["name"] for d in docs} == {"사양서1.pdf", "사양서2.pdf", "사양서3.pdf"}


def test_record_sync_log_endpoint(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    monkeypatch.setattr(routes, "storage", persisted)

    response = TestClient(app).post("/knowledge/sync-log", data={"product": "VXvue", "kind": "specification", "source": "alm_crawler", "status": "SUCCESS", "detail": "3 files"})

    assert response.status_code == 200
    latest = persisted.latest_sync("VXvue", "specification")
    assert latest["status"] == "SUCCESS"


def test_trigger_specification_sync_blocked_when_unavailable(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    monkeypatch.setattr(routes, "storage", persisted)
    import app.modules.impact_analyzer.vxvue_spec_sync as vxvue_spec
    monkeypatch.setattr(vxvue_spec, "is_available_on_this_host", lambda *a, **k: False)

    response = TestClient(app).post("/knowledge/sync/specification")

    assert response.status_code == 400


def test_trigger_specification_sync_blocked_when_already_running(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    persisted.sync_start("VXvue", "specification", "alm_crawler")
    monkeypatch.setattr(routes, "storage", persisted)

    response = TestClient(app).post("/knowledge/sync/specification")

    assert response.status_code == 409


def test_start_analysis_requires_file_or_notes():
    response = TestClient(app).post("/analyses", data={"product": "VXvue"})
    assert response.status_code == 400


def test_delete_document_removes_row_and_file(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "app.db")
    file_path = tmp_path / "spec.pdf"
    file_path.write_bytes(b"%PDF-")
    doc_id = storage.add_document("specification", "VXvue", "1.0", "Rev.1", "spec.pdf", file_path)
    monkeypatch.setattr(routes, "storage", storage)

    response = TestClient(app).post(f"/knowledge/delete/{doc_id}", follow_redirects=False)

    assert response.status_code == 303
    assert storage.get_document(doc_id) is None
    assert not file_path.exists()


def test_delete_missing_document_returns_404(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(routes, "storage", storage)

    response = TestClient(app).post("/knowledge/delete/999", follow_redirects=False)

    assert response.status_code == 404


def test_tokens_used_since_sums_done_analyses(tmp_path):
    storage = Storage(tmp_path / "app.db")
    old = _result("old")
    old["token_usage"] = {"total_tokens": 100}
    new = _result("new")
    new["token_usage"] = {"total_tokens": 250}
    storage.create_analysis("old")
    storage.update_analysis("old", "DONE", result=old)
    storage.create_analysis("new")
    storage.update_analysis("new", "DONE", result=new)
    storage.create_analysis("running", status="RUNNING")

    assert storage.tokens_used_since("1970-01-01T00:00:00+00:00") == 350


def test_start_analysis_blocked_when_daily_token_limit_exceeded(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    used = _result("used-up")
    used["token_usage"] = {"total_tokens": 999}
    persisted.create_analysis("used-up")
    persisted.update_analysis("used-up", "DONE", result=used)
    monkeypatch.setattr(routes, "storage", persisted)
    routes.get_settings().raw.setdefault("analysis", {})["daily_token_limit"] = 500
    try:
        response = TestClient(app).post("/analyses", files={"change_files": ("c.pdf", b"%PDF-", "application/pdf")}, data={"product": "VXvue"})
        assert response.status_code == 429
    finally:
        routes.get_settings().raw["analysis"]["daily_token_limit"] = 0


def test_analysis_history_renders_persisted_results(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    persisted.create_analysis("history-job")
    persisted.update_analysis("history-job", "DONE", result=_result("history-job"))
    monkeypatch.setattr(routes, "storage", persisted)

    response = TestClient(app).get("/analyses")

    assert response.status_code == 200
    assert "history-job" in response.text
    assert "XLSX" in response.text
