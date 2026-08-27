"""Authentication and my-account behaviour (spec section 53)."""
from __future__ import annotations

GENERIC = "아이디 또는 비밀번호가 올바르지 않습니다."


def test_login_success_sets_session_cookie(client, make_user):
    make_user("hong", "홍길동")
    response = client.post(
        "/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["login_id"] == "hong"
    assert body["display_name"] == "홍길동"
    assert body["is_admin"] is False
    assert "qamh_session" in response.cookies
    # The password hash must never travel to the client.
    assert "password_hash" not in body


def test_login_is_case_insensitive_on_login_id(client, make_user):
    make_user("hong", "홍길동")
    assert (
        client.post(
            "/api/auth/login", json={"login_id": "HONG", "password": "Passw0rd!"}
        ).status_code
        == 200
    )


def test_login_wrong_password_is_rejected(client, make_user):
    make_user("hong", "홍길동")
    response = client.post(
        "/api/auth/login", json={"login_id": "hong", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == GENERIC


def test_unknown_user_gives_the_same_message_as_a_bad_password(client, make_user):
    make_user("hong", "홍길동")
    unknown = client.post(
        "/api/auth/login", json={"login_id": "nobody", "password": "Passw0rd!"}
    )
    bad_password = client.post(
        "/api/auth/login", json={"login_id": "hong", "password": "nope"}
    )
    assert unknown.status_code == bad_password.status_code == 401
    # Spec section 50: never disclose which half was wrong.
    assert unknown.json()["detail"] == bad_password.json()["detail"] == GENERIC


def test_inactive_user_cannot_log_in(client, make_user):
    make_user("kim", "김철수", is_active=False)
    response = client.post(
        "/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == GENERIC


def test_protected_endpoint_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/products").status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_logout_invalidates_the_session(client, make_user):
    make_user("hong", "홍길동")
    client.post("/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"})
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_login_failure_is_recorded_in_login_history_and_audit(client, make_user):
    make_user("admin", "QA Admin", admin=True)
    client.post("/api/auth/login", json={"login_id": "admin", "password": "nope"})
    client.post("/api/auth/login", json={"login_id": "admin", "password": "Passw0rd!"})

    logs = client.get("/api/audit-logs", params={"action": "LOGIN_FAILURE"}).json()
    assert len(logs) == 1
    assert logs[0]["detail"] == "bad_password"
    assert logs[0]["action_label"] == "로그인 실패"


def test_last_login_at_is_updated(client, make_user):
    make_user("hong", "홍길동")
    assert (
        client.post(
            "/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"}
        ).json()["last_login_at"]
        is not None
    )


def test_user_can_change_own_password(client, make_user):
    make_user("hong", "홍길동")
    client.post("/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"})

    assert (
        client.post(
            "/api/auth/change-password",
            json={"current_password": "wrong", "new_password": "Brand-New-1"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/change-password",
            json={"current_password": "Passw0rd!", "new_password": "short"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/change-password",
            json={"current_password": "Passw0rd!", "new_password": "Brand-New-1"},
        ).status_code
        == 200
    )

    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"login_id": "hong", "password": "Brand-New-1"}
        ).status_code
        == 200
    )


def test_must_change_password_blocks_document_work_until_changed(
    client, make_user, catalog
):
    """A user handed a temporary password can log in and change it, but cannot
    create documents until they do."""
    client.post("/api/auth/logout")
    make_user("temp", "임시사용자", password="Temp-1234", must_change_password=True)
    me = client.post(
        "/api/auth/login", json={"login_id": "temp", "password": "Temp-1234"}
    ).json()
    assert me["must_change_password"] is True

    blocked = client.post(
        "/api/documents",
        json={
            "product_id": catalog["product"]["id"],
            "category_id": catalog["category"]["id"],
            "name": "Blocked Manual",
        },
    )
    assert blocked.status_code == 428

    assert (
        client.post(
            "/api/auth/change-password",
            json={"current_password": "Temp-1234", "new_password": "Chosen-9876"},
        ).status_code
        == 200
    )
    allowed = client.post(
        "/api/documents",
        json={
            "product_id": catalog["product"]["id"],
            "category_id": catalog["category"]["id"],
            "name": "Allowed Manual",
        },
    )
    assert allowed.status_code == 201
