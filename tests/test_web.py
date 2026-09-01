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
    assert 'href="/impact-analyzer/guide"' in response.text
    assert 'href="/manual-review"' not in response.text
    assert "Regression 분석" in response.text


def test_impact_and_manual_guides_are_separate():
    client = TestClient(app)
    impact = client.get("/impact-analyzer/guide")
    manual = client.get("/manual-review/guide")

    assert impact.status_code == 200
    assert "Regression 영향 분석 사용법" in impact.text
    assert "매뉴얼 개정 검증 사용법" not in impact.text
    assert manual.status_code == 200
    assert "매뉴얼 개정 검증 사용법" in manual.text
    assert "Regression 영향 분석 사용법" not in manual.text


def test_legacy_guide_redirects_to_impact_guide():
    response = TestClient(app).get("/guide", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == "/impact-analyzer/guide"


def test_knowledge_is_presented_as_shared_workspace():
    response = TestClient(app).get("/knowledge")
    assert response.status_code == 200
    assert "공용 Knowledge" in response.text
    assert 'href="/impact-analyzer"' in response.text
    assert 'href="/manual-review"' in response.text
