from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.storage import Storage
from app.main import app
from app.modules.cost_dashboard import router as cost_dashboard_router
from app.modules.impact_analyzer import router as impact_analyzer_router


def _impact_result(total_tokens: int, cache_hit: bool | None) -> dict:
    result = {
        "analysis_id": "x",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "change_file": "change.docx",
        "specification_file": "spec.pdf",
        "testcase_file": "tc.xlsx",
        "change": {"changed_features": []},
        "total_tc": 1,
        "candidate_tc": 1,
        "decisions": [],
        "token_usage": {"total_tokens": total_tokens},
    }
    if cache_hit is not None:
        result["ai_audit"] = {"cache_hit": cache_hit}
    return result


def _manual_review_result(total_tokens: int, revision_id: int = 1, ai_audit: dict | None = None) -> dict:
    result = {
        "revision_id": revision_id,
        "round_number": 1,
        "total_changes": 3,
        "functional_changes": 2,
        "decision_counts": {},
        "prior_open_comments": [],
        "release_scope_total": 0,
        "release_scope_missing_suspected": 0,
        "cross_manual_review_required": 0,
        "token_usage": {"total_tokens": total_tokens},
    }
    if ai_audit is not None:
        result["ai_audit"] = ai_audit
    return result


def test_cost_dashboard_stats_aggregates_by_module_and_day(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("impact-1", module="impact_analyzer", request={"product": "VXvue"})
    storage.update_analysis("impact-1", "DONE", result=_impact_result(100, cache_hit=True))
    storage.create_analysis("manual-1", module="manual_review")
    storage.update_analysis("manual-1", "DONE", result=_manual_review_result(50))

    stats = storage.cost_dashboard_stats(days=30)

    assert stats["modules"]["impact_analyzer"] == {"tokens": 100, "count": 1}
    assert stats["modules"]["manual_review"] == {"tokens": 50, "count": 1}
    assert len(stats["daily"]) == 1
    assert stats["daily"][0]["tokens"] == 150
    recent_products = {item["id"]: item["product"] for item in stats["recent"]}
    assert recent_products["impact-1"] == "VXvue"


def test_cost_dashboard_infers_module_for_legacy_rows_without_module_column(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("legacy", module=None)
    storage.update_analysis("legacy", "DONE", result=_manual_review_result(20))

    stats = storage.cost_dashboard_stats(days=30)

    assert stats["modules"]["manual_review"]["tokens"] == 20


def test_cost_dashboard_cache_hit_rate_ignores_analyses_without_cache_data(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("hit", module="impact_analyzer")
    storage.update_analysis("hit", "DONE", result=_impact_result(10, cache_hit=True))
    storage.create_analysis("miss", module="impact_analyzer")
    storage.update_analysis("miss", "DONE", result=_impact_result(10, cache_hit=False))
    storage.create_analysis("manual", module="manual_review")
    storage.update_analysis("manual", "DONE", result=_manual_review_result(10))

    stats = storage.cost_dashboard_stats(days=30)

    assert stats["cache_sample_size"] == 2
    assert stats["cache_hit_rate"] == 0.5


def test_cost_dashboard_cache_hit_rate_includes_manual_review_call_counts(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("impact-hit", module="impact_analyzer")
    storage.update_analysis("impact-hit", "DONE", result=_impact_result(10, cache_hit=True))
    storage.create_analysis("manual-1", module="manual_review")
    storage.update_analysis(
        "manual-1", "DONE",
        result=_manual_review_result(10, ai_audit={"request_count": 1, "cache_hit_count": 1}),
    )

    stats = storage.cost_dashboard_stats(days=30)

    # impact: 1 hit / 1 call. manual: 1 hit / (1 hit + 1 실제 요청) = 1/2 calls. 합계 2 hits / 3 calls.
    assert stats["cache_sample_size"] == 3
    assert stats["cache_hit_rate"] == 2 / 3
    recent_by_id = {item["id"]: item for item in stats["recent"]}
    assert recent_by_id["manual-1"]["cache_hits"] == 1
    assert recent_by_id["manual-1"]["cache_calls"] == 2


def test_cost_dashboard_stats_excludes_analyses_older_than_window(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("old", module="impact_analyzer")
    storage.update_analysis("old", "DONE", result=_impact_result(999, cache_hit=None))
    with storage.connect() as db:
        db.execute("UPDATE analyses SET created_at=? WHERE id=?", ("2000-01-01T00:00:00+00:00", "old"))

    stats = storage.cost_dashboard_stats(days=30)

    assert stats["modules"] == {}
    assert stats["daily"] == []


def test_cost_dashboard_route_renders_module_and_cache_summary(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.create_analysis("impact-1", module="impact_analyzer", request={"product": "VXvue"})
    storage.update_analysis("impact-1", "DONE", result=_impact_result(100, cache_hit=True))
    monkeypatch.setattr(cost_dashboard_router, "storage", storage)
    monkeypatch.setattr(impact_analyzer_router, "storage", storage)

    response = TestClient(app).get("/cost-dashboard")

    assert response.status_code == 200
    assert "Regression 영향 분석" in response.text
    assert "VXvue" in response.text
    assert "100" in response.text


def test_cost_dashboard_route_respects_days_query_param(monkeypatch, tmp_path):
    storage = Storage(tmp_path / "app.db")
    monkeypatch.setattr(cost_dashboard_router, "storage", storage)
    monkeypatch.setattr(impact_analyzer_router, "storage", storage)

    response = TestClient(app).get("/cost-dashboard?days=7")

    assert response.status_code == 200
    assert "최근 7일" in response.text


def test_cost_dashboard_linked_from_other_modules():
    client = TestClient(app)
    for path in ("/impact-analyzer", "/manual-review", "/knowledge"):
        assert 'href="/cost-dashboard"' in client.get(path).text
