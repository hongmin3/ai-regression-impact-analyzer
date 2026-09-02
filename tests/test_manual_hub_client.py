"""매뉴얼 서버(하위 서비스) 연동 테스트.

가장 중요한 것은 **연동이 실패해도 핵심 앱이 계속 동작하는가**다. 두 시스템은 별도 배포
단위이고, 하위 서비스가 내려갔다고 매뉴얼 개정 검증이 실패하면 저장소만 합치고 장애는
전파되는 최악의 결합이 된다.

실제 네트워크를 타지 않는다 — `httpx.MockTransport` 로 매뉴얼 서버를 흉내 낸다.
"""
import httpx
import pytest

from app.core import manual_hub_client
from app.core.config import build_settings
from app.core.manual_hub_client import HubDocument, ManualHubClient

BASE = "http://127.0.0.1/manual-hub/api"

PRODUCTS = [
    {"id": "p-1", "name": "VXvue", "code": "VX"},
    {"id": "p-2", "name": "Other", "code": "OT"},
]
DOCUMENTS = [
    {"id": "d-1", "name": "Service Manual", "category_name": "Service Manual",
     "current_revision": "V1.0.12W1", "current_version_id": "v-1"},
    {"id": "d-2", "name": "Operation Manual", "category_name": "Operation Manual",
     "current_revision": "Rev.1.3", "current_version_id": "v-2"},
    # Current 가 없는 문서는 대조 대상이 될 수 없다.
    {"id": "d-3", "name": "Draft Manual", "category_name": "Other",
     "current_revision": None, "current_version_id": None},
]


def hub_transport(*, login_status=200, documents_status=200, download_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/auth/login"):
            return httpx.Response(login_status, json={"login_id": "svc"})
        if path.endswith("/products"):
            return httpx.Response(200, json=PRODUCTS)
        if path.endswith("/documents"):
            if documents_status != 200:
                return httpx.Response(documents_status, json={"detail": "nope"})
            product_id = request.url.params.get("product_id")
            return httpx.Response(200, json=[d for d in DOCUMENTS] if product_id == "p-1" else [])
        if path.endswith("/current/download"):
            if download_status != 200:
                return httpx.Response(download_status)
            return httpx.Response(200, content=b"manual bytes", headers={
                "content-disposition": "attachment; filename*=UTF-8''%EB%A7%A4%EB%89%B4%EC%96%BC.pdf",
            })
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def client_for(transport) -> ManualHubClient:
    return ManualHubClient(BASE, "svc", "pw", client=httpx.Client(transport=transport))


# --- 정상 경로 ------------------------------------------------------------- #

def test_finds_product_and_lists_documents_with_a_current_version():
    with client_for(hub_transport()) as hub:
        product_id = hub.find_product_id("vxvue")           # 대소문자 무시
        assert product_id == "p-1"
        documents = hub.documents(product_id)
    assert [d.name for d in documents] == ["Service Manual", "Operation Manual"]
    assert documents[0].current_revision == "V1.0.12W1"


def test_download_keeps_the_korean_file_name_and_extension(tmp_path):
    document = HubDocument("d-1", "Service Manual", "Service Manual", "V1", "v-1")
    with client_for(hub_transport()) as hub:
        path = hub.download_current(document, tmp_path)
    assert path is not None
    assert path.read_bytes() == b"manual bytes"
    # 확장자가 살아야 파서가 형식별로 처리할 수 있고, 문서 id 접두어로 충돌을 막는다.
    assert path.name == "d-1_매뉴얼.pdf"


def test_unknown_product_returns_none():
    with client_for(hub_transport()) as hub:
        assert hub.find_product_id("없는제품") is None


# --- 실패 경로 — 여기가 핵심 --------------------------------------------- #

def test_login_failure_is_reported_not_raised():
    hub = client_for(hub_transport(login_status=401))
    assert hub.login() is False
    hub.close()


def test_connection_error_does_not_propagate():
    def refuse(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    hub = client_for(httpx.MockTransport(refuse))
    assert hub.login() is False
    assert hub.find_product_id("VXvue") is None
    assert hub.documents("p-1") == []
    hub.close()


def test_document_listing_failure_returns_empty():
    with client_for(hub_transport(documents_status=500)) as hub:
        assert hub.documents("p-1") == []


def test_download_failure_returns_none(tmp_path):
    document = HubDocument("d-1", "Service Manual", "Service Manual", "V1", "v-1")
    with client_for(hub_transport(download_status=410)) as hub:
        assert hub.download_current(document, tmp_path) is None


# --- 설정 게이트 ------------------------------------------------------------ #

def settings_with(tmp_path, api_url: str, user: str, password: str):
    root = tmp_path / "project"
    root.mkdir()
    (root / "config.yaml").write_text(
        "storage:\n"
        "  upload_dir: data/uploads\n  specification_dir: data/specifications\n"
        "  testcase_dir: data/testcases\n  index_dir: data/indexes\n"
        "  report_dir: output/reports\n  export_dir: output/exports\n"
        "  generated_tc_dir: output/generated_tc\n  log_dir: output/logs\n"
        "  manual_revision_dir: data/manual_revisions\n"
        "  manual_review_comment_dir: output/comments\n"
        "  manual_hub_cache_dir: data/manual_hub_cache\n"
        f'services:\n  manual_hub:\n    api_url: "{api_url}"\n',
        encoding="utf-8")
    settings = build_settings(root)
    settings.secrets.manual_hub_user = user
    settings.secrets.manual_hub_password = password
    return settings


@pytest.mark.parametrize("api_url,user,password", [
    ("", "svc", "pw"),          # 주소 없음
    (BASE, "", "pw"),           # 계정 없음
    (BASE, "svc", ""),          # 비밀번호 없음
])
def test_integration_stays_off_until_fully_configured(tmp_path, api_url, user, password):
    settings = settings_with(tmp_path, api_url, user, password)
    assert manual_hub_client.from_settings(settings) is None


def test_fully_configured_returns_a_client(tmp_path):
    settings = settings_with(tmp_path, BASE, "svc", "pw")
    client = manual_hub_client.from_settings(settings, client=httpx.Client(transport=hub_transport()))
    assert client is not None
    assert client.base_url == BASE
    client.close()
