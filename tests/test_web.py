from fastapi.testclient import TestClient

from app.main import app


def test_health():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hub_links_to_qa_modules():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "<nav>" not in response.text
    assert 'href="/impact-analyzer"' in response.text
    assert 'href="/manual-review"' in response.text


def test_impact_analyzer_has_dedicated_entry_route():
    response = TestClient(app).get("/impact-analyzer")
    assert response.status_code == 200
    assert "<nav>" in response.text
    assert 'href="/"' in response.text
    assert "Regression 분석" in response.text
