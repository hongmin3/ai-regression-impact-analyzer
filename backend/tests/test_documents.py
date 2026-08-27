"""Documents, versions, current-version policy, download, archive and search."""
from __future__ import annotations

import hashlib


def _make_document(client, catalog, name="Operation Manual"):
    response = client.post(
        "/api/documents",
        json={
            "product_id": catalog["product"]["id"],
            "category_id": catalog["category"]["id"],
            "name": name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, document_id, content: bytes, *, revision=None, version=None, **extra):
    data = {k: v for k, v in extra.items() if v is not None}
    if revision:
        data["revision"] = revision
    if version:
        data["version"] = version
    return client.post(
        f"/api/documents/{document_id}/versions",
        files={"file": ("manual.pdf", content, "application/pdf")},
        data=data,
    )


# --------------------------------------------------------------------------- #
# product / document creation
# --------------------------------------------------------------------------- #
def test_product_and_document_creation(admin_client, catalog):
    products = admin_client.get("/api/products").json()
    assert [p["name"] for p in products] == ["Bellalun Viewer"]

    document = _make_document(admin_client, catalog)
    assert document["product_name"] == "Bellalun Viewer"
    assert document["category_name"] == "Operation Manual"
    assert document["current_version_id"] is None
    assert document["version_count"] == 0


def test_duplicate_document_name_within_a_product_is_rejected(admin_client, catalog):
    _make_document(admin_client, catalog)
    clash = admin_client.post(
        "/api/documents",
        json={
            "product_id": catalog["product"]["id"],
            "category_id": catalog["category"]["id"],
            "name": "operation manual",
        },
    )
    assert clash.status_code == 409


def test_same_document_name_is_allowed_under_a_different_product(admin_client, catalog):
    _make_document(admin_client, catalog)
    other = admin_client.post("/api/products", json={"name": "VXvue"}).json()
    ok = admin_client.post(
        "/api/documents",
        json={
            "product_id": other["id"],
            "category_id": catalog["category"]["id"],
            "name": "Operation Manual",
        },
    )
    assert ok.status_code == 201


def test_normal_user_can_create_documents_and_upload(client, make_user, admin_client, catalog):
    """Spec section 9: document work is open to every logged-in user."""
    admin_client.post("/api/auth/logout")
    make_user("hong", "홍길동")
    assert (
        client.post(
            "/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"}
        ).status_code
        == 200
    )
    document = _make_document(client, catalog)
    assert _upload(client, document["id"], b"%PDF-1.7\nx\n", version="V1.0").status_code == 201


# --------------------------------------------------------------------------- #
# upload / uploader attribution
# --------------------------------------------------------------------------- #
def test_uploaded_by_comes_from_the_logged_in_user_not_from_input(
    admin_client, catalog, make_user
):
    document = _make_document(admin_client, catalog)
    admin_client.post("/api/auth/logout")
    make_user("hong", "홍길동")
    admin_client.post(
        "/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"}
    )

    body = _upload(
        admin_client,
        document["id"],
        b"%PDF-1.7\nfirst\n",
        version="V1.0.12W1",
        revision_date="2026-07-10",
        revision_description="Image Tool 설명 변경",
        # Even if a client tries to spoof the uploader, the server ignores it.
        uploaded_by_display_name="누군가",
    ).json()

    assert body["version"]["uploaded_by_display_name"] == "홍길동"
    assert body["version"]["uploaded_by_login_id"] == "hong"
    assert body["version"]["revision_date"] == "2026-07-10"
    assert body["became_current"] is True


def test_sha256_is_computed_and_stored(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    content = b"%PDF-1.7\nhash-me\n"
    body = _upload(admin_client, document["id"], content, version="V1.0").json()
    assert body["version"]["stored_file"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert body["version"]["stored_file"]["byte_size"] == len(content)
    assert body["version"]["stored_file"]["original_file_name"] == "manual.pdf"


def test_upload_requires_a_revision_or_a_version(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    response = _upload(admin_client, document["id"], b"%PDF-1.7\nx\n")
    assert response.status_code == 400
    assert "Revision" in response.json()["detail"]


def test_disallowed_extension_is_refused(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    response = admin_client.post(
        f"/api/documents/{document['id']}/versions",
        files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")},
        data={"version": "V1.0"},
    )
    assert response.status_code == 400
    assert "exe" in response.json()["detail"]


def test_content_that_does_not_match_the_extension_is_refused(admin_client, catalog):
    """A .pdf that is not a PDF never reaches storage."""
    document = _make_document(admin_client, catalog)
    response = admin_client.post(
        f"/api/documents/{document['id']}/versions",
        files={"file": ("fake.pdf", b"MZ\x90\x00 this is a windows binary", "application/pdf")},
        data={"version": "V1.0"},
    )
    assert response.status_code == 400
    assert "일치하지 않습니다" in response.json()["detail"]


def test_duplicate_hash_warns_but_still_registers(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    content = b"%PDF-1.7\nidentical\n"
    first = _upload(admin_client, document["id"], content, version="V1.0").json()
    assert first["duplicate_of"] == []
    assert first["warning"] is None

    second = _upload(admin_client, document["id"], content, version="V1.1")
    assert second.status_code == 201
    body = second.json()
    assert len(body["duplicate_of"]) == 1
    assert body["duplicate_of"][0]["version_label"] == "V1.0"
    assert "이미 등록되어" in body["warning"]

    # Warned, not blocked -- both versions exist.
    assert len(admin_client.get(f"/api/documents/{document['id']}/versions").json()) == 2


# --------------------------------------------------------------------------- #
# current version policy
# --------------------------------------------------------------------------- #
def test_newest_upload_becomes_current_and_history_is_kept(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    v1 = _upload(admin_client, document["id"], b"%PDF-1.7\nv1\n", version="V1.0.11").json()
    v2 = _upload(admin_client, document["id"], b"%PDF-1.7\nv2\n", version="V1.0.12").json()
    v3 = _upload(admin_client, document["id"], b"%PDF-1.7\nv3\n", version="V1.0.13").json()

    detail = admin_client.get(f"/api/documents/{document['id']}").json()
    assert detail["current_version_id"] == v3["version"]["id"]
    assert detail["current_version_label"] == "V1.0.13"
    assert detail["version_count"] == 3

    labels = {v["version"]: v["is_current"] for v in detail["versions"]}
    assert labels == {"V1.0.11": False, "V1.0.12": False, "V1.0.13": True}

    # Every earlier file is still downloadable -- nothing was overwritten.
    for uploaded in (v1, v2, v3):
        got = admin_client.get(
            f"/api/documents/{document['id']}/versions/"
            f"{uploaded['version']['id']}/download"
        )
        assert got.status_code == 200


def test_legacy_upload_can_be_demoted_with_set_as_current(admin_client, catalog):
    """The spec's exact scenario: V1.0.13 is current, an old V1.0.8 turns up
    later and lands as current, and the user puts V1.0.13 back."""
    document = _make_document(admin_client, catalog)
    _upload(admin_client, document["id"], b"%PDF-1.7\na\n", version="V1.0.12").json()
    current = _upload(
        admin_client, document["id"], b"%PDF-1.7\nb\n", version="V1.0.13"
    ).json()
    legacy = _upload(
        admin_client, document["id"], b"%PDF-1.7\nlegacy\n", version="V1.0.8"
    ).json()

    # Default policy: the newest upload became current, even though it is older.
    assert (
        admin_client.get(f"/api/documents/{document['id']}").json()[
            "current_version_label"
        ]
        == "V1.0.8"
    )

    restored = admin_client.post(
        f"/api/documents/{document['id']}/set-current",
        json={"version_id": current["version"]["id"]},
    )
    assert restored.status_code == 200
    assert restored.json()["current_version_label"] == "V1.0.13"

    # Nothing was deleted by the switch.
    versions = admin_client.get(f"/api/documents/{document['id']}/versions").json()
    assert {v["version"] for v in versions} == {"V1.0.12", "V1.0.13", "V1.0.8"}
    assert (
        admin_client.get(
            f"/api/documents/{document['id']}/versions/"
            f"{legacy['version']['id']}/download"
        ).status_code
        == 200
    )


def test_upload_with_set_as_current_false_leaves_current_alone(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    keep = _upload(admin_client, document["id"], b"%PDF-1.7\nkeep\n", version="V2.0").json()
    added = _upload(
        admin_client,
        document["id"],
        b"%PDF-1.7\nold\n",
        version="V1.0",
        set_as_current="false",
    ).json()
    assert added["became_current"] is False
    assert (
        admin_client.get(f"/api/documents/{document['id']}").json()["current_version_id"]
        == keep["version"]["id"]
    )


def test_set_current_rejects_a_version_from_another_document(admin_client, catalog):
    a = _make_document(admin_client, catalog, "Operation Manual")
    b = _make_document(admin_client, catalog, "Service Manual")
    foreign = _upload(admin_client, b["id"], b"%PDF-1.7\nx\n", version="V1.0").json()
    response = admin_client.post(
        f"/api/documents/{a['id']}/set-current",
        json={"version_id": foreign["version"]["id"]},
    )
    assert response.status_code == 404


def test_set_current_on_the_already_current_version_is_a_conflict(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    v = _upload(admin_client, document["id"], b"%PDF-1.7\nx\n", version="V1.0").json()
    assert (
        admin_client.post(
            f"/api/documents/{document['id']}/set-current",
            json={"version_id": v["version"]["id"]},
        ).status_code
        == 409
    )


# --------------------------------------------------------------------------- #
# download / preview
# --------------------------------------------------------------------------- #
def test_download_returns_the_original_bytes_and_file_name(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    content = b"%PDF-1.7\ndownload-me\n"
    uploaded = admin_client.post(
        f"/api/documents/{document['id']}/versions",
        files={
            "file": (
                "(매뉴얼) Bellalun Viewer Operation Manual.V1.0.12W1_KO.pdf",
                content,
                "application/pdf",
            )
        },
        data={"version": "V1.0.12W1"},
    ).json()

    response = admin_client.get(
        f"/api/documents/{document['id']}/versions/"
        f"{uploaded['version']['id']}/download"
    )
    assert response.status_code == 200
    assert response.content == content
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    # Korean file name survives via RFC 6266 filename*.
    assert "filename*=UTF-8''" in disposition
    assert "%EB%A7%A4%EB%89%B4%EC%96%BC" in disposition


def test_preview_is_inline_for_pdf(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    uploaded = _upload(
        admin_client, document["id"], b"%PDF-1.7\npreview\n", version="V1.0"
    ).json()
    assert uploaded["version"]["can_preview"] is True
    response = admin_client.get(
        f"/api/documents/{document['id']}/versions/"
        f"{uploaded['version']['id']}/preview"
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["content-type"] == "application/pdf"


def test_download_current_shortcut(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    assert (
        admin_client.get(f"/api/documents/{document['id']}/current/download").status_code
        == 404
    )
    _upload(admin_client, document["id"], b"%PDF-1.7\ncur\n", version="V9")
    assert (
        admin_client.get(f"/api/documents/{document['id']}/current/download").status_code
        == 200
    )


def test_download_requires_authentication(client, admin_client, catalog):
    document = _make_document(admin_client, catalog)
    uploaded = _upload(admin_client, document["id"], b"%PDF-1.7\nx\n", version="V1").json()
    admin_client.post("/api/auth/logout")
    assert (
        admin_client.get(
            f"/api/documents/{document['id']}/versions/"
            f"{uploaded['version']['id']}/download"
        ).status_code
        == 401
    )


# --------------------------------------------------------------------------- #
# archive / restore
# --------------------------------------------------------------------------- #
def test_document_archive_and_restore_keeps_versions(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    uploaded = _upload(admin_client, document["id"], b"%PDF-1.7\nx\n", version="V1").json()

    archived = admin_client.post(f"/api/documents/{document['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    # Hidden from the default list but still readable and downloadable.
    assert admin_client.get("/api/documents").json() == []
    assert len(admin_client.get("/api/documents", params={"status": "all"}).json()) == 1
    assert (
        admin_client.get(
            f"/api/documents/{document['id']}/versions/"
            f"{uploaded['version']['id']}/download"
        ).status_code
        == 200
    )

    # No new versions while archived.
    assert _upload(
        admin_client, document["id"], b"%PDF-1.7\ny\n", version="V2"
    ).status_code == 409

    restored = admin_client.post(f"/api/documents/{document['id']}/restore")
    assert restored.json()["status"] == "active"
    assert restored.json()["version_count"] == 1
    assert _upload(
        admin_client, document["id"], b"%PDF-1.7\ny\n", version="V2"
    ).status_code == 201


def test_current_version_cannot_be_archived(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    v1 = _upload(admin_client, document["id"], b"%PDF-1.7\na\n", version="V1").json()
    v2 = _upload(admin_client, document["id"], b"%PDF-1.7\nb\n", version="V2").json()

    blocked = admin_client.post(
        f"/api/documents/{document['id']}/versions/{v2['version']['id']}/archive"
    )
    assert blocked.status_code == 409

    ok = admin_client.post(
        f"/api/documents/{document['id']}/versions/{v1['version']['id']}/archive"
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "archived"

    # An archived version cannot be promoted to current until restored.
    assert (
        admin_client.post(
            f"/api/documents/{document['id']}/set-current",
            json={"version_id": v1["version"]["id"]},
        ).status_code
        == 409
    )
    assert (
        admin_client.post(
            f"/api/documents/{document['id']}/versions/{v1['version']['id']}/restore"
        ).status_code
        == 200
    )
    assert (
        admin_client.post(
            f"/api/documents/{document['id']}/set-current",
            json={"version_id": v1["version"]["id"]},
        ).status_code
        == 200
    )


# --------------------------------------------------------------------------- #
# metadata edit / search
# --------------------------------------------------------------------------- #
def test_version_metadata_edit(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    uploaded = _upload(admin_client, document["id"], b"%PDF-1.7\nx\n", version="V1").json()
    updated = admin_client.patch(
        f"/api/documents/{document['id']}/versions/{uploaded['version']['id']}",
        json={
            "revision": "Rev.1.3",
            "document_number": "VW-BLV-OM-001",
            "language": "KO",
            "revision_date": "2026-07-10",
            "revision_description": "Setting 내용 변경",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["document_number"] == "VW-BLV-OM-001"
    assert updated.json()["revision_date"] == "2026-07-10"


def test_search_matches_across_metadata(admin_client, catalog):
    document = _make_document(admin_client, catalog)
    admin_client.post(
        f"/api/documents/{document['id']}/versions",
        files={
            "file": (
                "Bellalun Viewer Operation Manual.V1.0.12W1_KO.pdf",
                b"%PDF-1.7\nsearch\n",
                "application/pdf",
            )
        },
        data={
            "version": "V1.0.12W1",
            "revision": "Rev.A",
            "document_number": "VW-BLV-OM-001",
            "language": "KO",
            "revision_date": "2026-07-10",
        },
    )

    for params in (
        {"q": "bellalun"},
        {"q": "V1.0.12W1"},
        {"q": "VW-BLV-OM"},
        {"document_number": "OM-001"},
        {"revision": "rev.a"},
        {"language": "ko"},
        {"file_name": "operation manual"},
        {"uploaded_by": "QA Admin"},
        {"revision_date_from": "2026-07-01", "revision_date_to": "2026-07-31"},
        {"current_only": True},
    ):
        hits = admin_client.get("/api/search", params=params).json()
        assert len(hits) == 1, f"no hit for {params}"
        assert hits[0]["document_name"] == "Operation Manual"
        assert hits[0]["is_current"] is True

    assert admin_client.get("/api/search", params={"q": "nothing-here"}).json() == []


def test_search_finds_a_document_with_no_versions_yet(admin_client, catalog):
    _make_document(admin_client, catalog, "QC Manual")
    hits = admin_client.get("/api/search", params={"q": "QC"}).json()
    assert len(hits) == 1
    assert hits[0]["version_id"] is None
    assert hits[0]["is_current"] is False
