"""Audit trail and dashboard aggregation."""
from __future__ import annotations


def _document_with_versions(client, catalog):
    document = client.post(
        "/api/documents",
        json={
            "product_id": catalog["product"]["id"],
            "category_id": catalog["category"]["id"],
            "name": "Operation Manual",
        },
    ).json()
    v1 = client.post(
        f"/api/documents/{document['id']}/versions",
        files={"file": ("m.pdf", b"%PDF-1.7\na\n", "application/pdf")},
        data={"version": "V1.0"},
    ).json()
    v2 = client.post(
        f"/api/documents/{document['id']}/versions",
        files={"file": ("m.pdf", b"%PDF-1.7\nb\n", "application/pdf")},
        data={"version": "V2.0"},
    ).json()
    return document, v1, v2


def test_every_required_event_is_audited(admin_client, catalog):
    document, v1, v2 = _document_with_versions(admin_client, catalog)
    admin_client.post(
        f"/api/documents/{document['id']}/set-current",
        json={"version_id": v1["version"]["id"]},
    )
    admin_client.get(
        f"/api/documents/{document['id']}/versions/{v2['version']['id']}/download"
    )
    admin_client.post(f"/api/documents/{document['id']}/archive")
    admin_client.post(f"/api/documents/{document['id']}/restore")
    admin_client.post(
        "/api/users",
        json={"login_id": "hong", "display_name": "홍길동", "password": "Initial-123"},
    )

    actions = {log["action"] for log in admin_client.get("/api/audit-logs").json()}
    for required in (
        "LOGIN",
        "PRODUCT_CREATE",
        "CATEGORY_CREATE",
        "DOCUMENT_CREATE",
        "VERSION_UPLOAD",
        "CURRENT_VERSION_CHANGE",
        "DOCUMENT_DOWNLOAD",
        "DOCUMENT_ARCHIVE",
        "DOCUMENT_RESTORE",
        "USER_CREATE",
    ):
        assert required in actions, f"{required} was not audited"


def test_current_version_change_records_before_and_after(admin_client, catalog):
    document, v1, _ = _document_with_versions(admin_client, catalog)
    admin_client.post(
        f"/api/documents/{document['id']}/set-current",
        json={"version_id": v1["version"]["id"]},
    )
    logs = admin_client.get(
        "/api/audit-logs", params={"action": "CURRENT_VERSION_CHANGE"}
    ).json()

    # Newest first: the manual switch, then the two automatic ones from upload.
    manual = logs[0]
    assert manual["before_value"]["current_version"] == "V2.0"
    assert manual["after_value"]["current_version"] == "V1.0"
    assert manual["detail"] == "사용자가 수동으로 Current 버전 변경"
    assert manual["actor_display_name"] == "QA Admin"
    assert manual["action_label"] == "Current 버전 변경"

    assert logs[1]["before_value"]["current_version"] == "V1.0"
    assert logs[1]["after_value"]["current_version"] == "V2.0"
    assert logs[-1]["before_value"]["current_version"] is None


def test_version_upload_audit_captures_uploader_and_hash(admin_client, catalog):
    _document_with_versions(admin_client, catalog)
    logs = admin_client.get("/api/audit-logs", params={"action": "VERSION_UPLOAD"}).json()
    assert len(logs) == 2
    after = logs[0]["after_value"]
    assert after["uploaded_by"] == "QA Admin"
    assert after["uploaded_by_login_id"] == "admin"
    assert len(after["sha256"]) == 64
    assert logs[0]["ip_address"] is not None


def test_audit_log_has_no_mutation_endpoints(admin_client, catalog):
    _document_with_versions(admin_client, catalog)
    log_id = admin_client.get("/api/audit-logs").json()[0]["id"]
    for method, path in (
        ("delete", f"/api/audit-logs/{log_id}"),
        ("patch", f"/api/audit-logs/{log_id}"),
        ("put", f"/api/audit-logs/{log_id}"),
        ("delete", "/api/audit-logs"),
    ):
        response = getattr(admin_client, method)(path)
        assert response.status_code in (404, 405), f"{method} {path} -> {response.status_code}"


def test_audit_filters(admin_client, catalog):
    document, _, _ = _document_with_versions(admin_client, catalog)
    assert (
        len(admin_client.get("/api/audit-logs", params={"actor": "QA Admin"}).json()) > 0
    )
    # DOCUMENT_CREATE + 2x VERSION_UPLOAD + 2x CURRENT_VERSION_CHANGE (each
    # upload auto-promotes, and each promotion is its own entry).
    by_document = admin_client.get(
        "/api/audit-logs", params={"document_id": document["id"]}
    ).json()
    assert len(by_document) == 5
    assert sorted(log["action"] for log in by_document) == [
        "CURRENT_VERSION_CHANGE",
        "CURRENT_VERSION_CHANGE",
        "DOCUMENT_CREATE",
        "VERSION_UPLOAD",
        "VERSION_UPLOAD",
    ]
    assert admin_client.get("/api/audit-logs", params={"actor": "없는사람"}).json() == []
    assert admin_client.get("/api/audit-logs", params={"q": "Operation"}).json() != []


def test_dashboard_counts_and_recent_lists(admin_client, catalog):
    document, _, v2 = _document_with_versions(admin_client, catalog)
    body = admin_client.get("/api/dashboard").json()

    counts = body["counts"]
    assert counts["products"] == 1
    assert counts["documents"] == 1
    assert counts["documents_active"] == 1
    assert counts["documents_with_current"] == 1
    assert counts["versions"] == 2
    assert counts["users_active"] == 1
    assert counts["storage_bytes"] > 0

    recent = body["recent_uploads"][0]
    assert recent["product_name"] == "Bellalun Viewer"
    assert recent["document_name"] == "Operation Manual"
    assert recent["version_label"] == "V2.0"
    assert recent["uploaded_by_display_name"] == "QA Admin"
    assert recent["is_current"] is True

    assert body["recent_current_changes"][0]["version_label"] == "V2.0"
    assert body["recent_documents"][0]["name"] == "Operation Manual"
    assert body["recent_activity"][0]["action_label"] != ""


def test_recent_updates_endpoint(admin_client, catalog):
    _document_with_versions(admin_client, catalog)
    rows = admin_client.get("/api/recent-updates", params={"limit": 5}).json()
    assert [r["version_label"] for r in rows] == ["V2.0", "V1.0"]


def test_settings_endpoint_reports_effective_limits(admin_client):
    body = admin_client.get("/api/settings").json()
    assert body["max_upload_mb"] == 500
    assert "pdf" in body["allowed_extensions"]
    assert "docx" in body["allowed_extensions"]
    assert body["session_lifetime_hours"] == 8
    assert body["storage_backend"] == "local"
