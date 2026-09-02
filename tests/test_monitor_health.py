"""운영 모니터는 감시 대상이 죽었을 때가 진짜 동작해야 하는 순간이다.

그래서 여기서는 "정상일 때 ok" 뿐 아니라 **조회가 실패했을 때 traceback 대신 alert 를
내는지**를 함께 검증한다. cron 로그에 스택만 남고 나머지 점검이 통째로 건너뛰어지면
모니터로서 의미가 없다.
"""
import json
import urllib.error

import pytest

from scripts import monitor_health


OK_HEALTH = {"status": "ok"}
OK_CONFIG = {"daily_token_usage": {"used": 10, "limit": 0, "exceeded": False}}
OK_OPERATIONS = {"database_integrity": "ok", "stale_jobs": 0, "last_sync": {"status": "DONE"}}


def fake_urls(mapping: dict[str, object]):
    """URL → 응답(dict) 또는 예외 인스턴스로 매핑하는 fetch_json 대역."""

    def fetch(url: str) -> dict:
        if url not in mapping:
            raise AssertionError(f"예상하지 못한 URL 조회: {url}")
        value = mapping[url]
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]

    return fetch


def run(monkeypatch, capsys, mapping, argv):
    monkeypatch.setattr(monitor_health, "fetch_json", fake_urls(mapping))
    monkeypatch.setattr(monitor_health.shutil, "disk_usage",
                        lambda _: type("U", (), {"free": 50 * 1024 ** 3})())
    monkeypatch.setattr("sys.argv", ["monitor_health.py", *argv])
    code = monitor_health.main()
    return code, json.loads(capsys.readouterr().out)


BASE = {
    "http://127.0.0.1:12000/health": OK_HEALTH,
    "http://127.0.0.1:12000/config/status": OK_CONFIG,
    "http://127.0.0.1:12000/operations/status": OK_OPERATIONS,
}


def test_all_ok_returns_zero(monkeypatch, capsys):
    code, payload = run(monkeypatch, capsys, BASE, [])
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["alerts"] == []


def test_extra_checks_are_reported_by_name(monkeypatch, capsys):
    mapping = {**BASE, "http://127.0.0.1/manual-hub/api/health": {"status": "ok", "app": "QA Manual Hub"}}
    code, payload = run(monkeypatch, capsys, mapping,
                        ["--check", "manual_hub=http://127.0.0.1/manual-hub/api/health"])
    assert code == 0
    assert payload["checks"] == {"manual_hub": "ok"}


def test_down_sub_service_alerts_without_crashing(monkeypatch, capsys):
    """매뉴얼 서버가 내려가도 핵심 앱 점검 결과는 그대로 나와야 한다."""
    mapping = {**BASE, "http://127.0.0.1/manual-hub/api/health": urllib.error.URLError("refused")}
    code, payload = run(monkeypatch, capsys, mapping,
                        ["--check", "manual_hub=http://127.0.0.1/manual-hub/api/health"])
    assert code == 1
    assert "check_failed:manual_hub" in payload["alerts"]
    assert payload["checks"]["manual_hub"] == "URLError"
    assert payload["daily_token_usage"] == OK_CONFIG["daily_token_usage"]


def test_core_app_down_produces_alert_not_traceback(monkeypatch, capsys):
    mapping = {url: urllib.error.URLError("refused") for url in BASE}
    code, payload = run(monkeypatch, capsys, mapping, [])
    assert code == 1
    assert "health_not_ok" in payload["alerts"]
    assert "config_status_unreachable" in payload["alerts"]
    assert "operations_status_unreachable" in payload["alerts"]


def test_unreachable_operations_does_not_fake_integrity_alerts(monkeypatch, capsys):
    """operations 조회가 실패했으면 무결성·stale 판정을 내리지 않는다 — 근거가 없다."""
    mapping = {**BASE, "http://127.0.0.1:12000/operations/status": urllib.error.URLError("refused")}
    code, payload = run(monkeypatch, capsys, mapping, [])
    assert code == 1
    assert payload["alerts"] == ["operations_status_unreachable"]


def test_existing_alerts_still_work(monkeypatch, capsys):
    mapping = {
        **BASE,
        "http://127.0.0.1:12000/config/status": {"daily_token_usage": {"exceeded": True}},
        "http://127.0.0.1:12000/operations/status": {"database_integrity": "failed", "stale_jobs": 2,
                                                     "last_sync": {"status": "FAILED"}},
    }
    code, payload = run(monkeypatch, capsys, mapping, [])
    assert code == 1
    for expected in ("daily_token_limit_exceeded", "database_integrity_failed",
                     "stale_jobs", "last_sync_failed"):
        assert expected in payload["alerts"]


def test_check_argument_requires_name_and_url():
    with pytest.raises(Exception):
        monitor_health.parse_check("http://127.0.0.1/health")
