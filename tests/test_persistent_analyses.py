from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.core.schemas import AnalysisResult, ChangeAnalysis
from app.core.storage import Storage
from app.web import routes


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


def test_analysis_history_renders_persisted_results(monkeypatch, tmp_path):
    persisted = Storage(tmp_path / "app.db")
    persisted.create_analysis("history-job")
    persisted.update_analysis("history-job", "DONE", result=_result("history-job"))
    monkeypatch.setattr(routes, "storage", persisted)

    response = TestClient(app).get("/analyses")

    assert response.status_code == 200
    assert "history-job" in response.text
    assert "XLSX" in response.text
