"""Admin user management and the permission boundary around it."""
from __future__ import annotations


def test_admin_creates_a_user_who_can_then_log_in(admin_client):
    created = admin_client.post(
        "/api/users",
        json={
            "login_id": "hong",
            "display_name": "홍길동",
            "password": "Initial-123",
            "role": "user",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["display_name"] == "홍길동"
    assert created.json()["must_change_password"] is True

    admin_client.post("/api/auth/logout")
    assert (
        admin_client.post(
            "/api/auth/login", json={"login_id": "hong", "password": "Initial-123"}
        ).status_code
        == 200
    )


def test_duplicate_login_id_is_rejected(admin_client):
    payload = {
        "login_id": "hong",
        "display_name": "홍길동",
        "password": "Initial-123",
    }
    assert admin_client.post("/api/users", json=payload).status_code == 201
    clash = admin_client.post(
        "/api/users",
        json={**payload, "display_name": "다른 사람"},
    )
    assert clash.status_code == 409
    # Case-insensitive uniqueness.
    assert (
        admin_client.post("/api/users", json={**payload, "login_id": "HONG"}).status_code
        == 409
    )


def test_short_password_is_rejected(admin_client):
    response = admin_client.post(
        "/api/users",
        json={"login_id": "kim", "display_name": "김철수", "password": "abc"},
    )
    assert response.status_code == 400
    assert "8자" in response.json()["detail"]


def test_normal_user_cannot_reach_user_management(client, make_user):
    make_user("hong", "홍길동")
    make_user("kim", "김철수")
    client.post("/api/auth/login", json={"login_id": "hong", "password": "Passw0rd!"})

    assert client.get("/api/users").status_code == 403
    assert (
        client.post(
            "/api/users",
            json={"login_id": "x", "display_name": "X", "password": "Passw0rd!"},
        ).status_code
        == 403
    )
    # Product/category management is admin-only too.
    assert client.post("/api/products", json={"name": "VXvue"}).status_code == 403
    assert (
        client.post("/api/categories", json={"name": "Release Note"}).status_code == 403
    )


def test_disable_then_enable_a_user(admin_client, make_user):
    user = make_user("kim", "김철수")

    disabled = admin_client.patch(
        f"/api/users/{user['id']}", json={"is_active": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    admin_client.post("/api/auth/logout")
    assert (
        admin_client.post(
            "/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"}
        ).status_code
        == 401
    )

    admin_client.post("/api/auth/login", json={"login_id": "admin", "password": "Passw0rd!"})
    enabled = admin_client.patch(f"/api/users/{user['id']}", json={"is_active": True})
    assert enabled.json()["is_active"] is True

    admin_client.post("/api/auth/logout")
    assert (
        admin_client.post(
            "/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"}
        ).status_code
        == 200
    )


def test_disabling_a_user_kills_their_live_session(client, make_user):
    """An open browser tab must lose access immediately, not at cookie expiry.

    Disabling revokes the session rows outright, so the stale cookie comes back
    401 (the SPA treats that as "go to the login screen") rather than 403.
    """
    make_user("admin", "QA Admin", admin=True)
    victim = make_user("kim", "김철수")

    client.post("/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"})
    victim_cookie = client.cookies.get("qamh_session")
    assert client.get("/api/auth/me").status_code == 200

    client.cookies.clear()
    client.post("/api/auth/login", json={"login_id": "admin", "password": "Passw0rd!"})
    client.patch(f"/api/users/{victim['id']}", json={"is_active": False})

    client.cookies.clear()
    client.cookies.set("qamh_session", victim_cookie)
    assert client.get("/api/auth/me").status_code == 401


def test_live_session_of_an_out_of_band_deactivation_is_refused(client, make_user):
    """If a user is deactivated outside the API (CLI, direct SQL) their session
    rows survive, so the request must still be rejected on the is_active check."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    make_user("kim", "김철수")
    client.post("/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"})
    assert client.get("/api/auth/me").status_code == 200

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.login_id == "kim"))
        assert user is not None
        user.is_active = False
        db.commit()

    response = client.get("/api/auth/me")
    assert response.status_code == 403
    assert "비활성화" in response.json()["detail"]


def test_password_reset_issues_a_working_temporary_password(admin_client, make_user):
    user = make_user("kim", "김철수")
    reset = admin_client.post(
        f"/api/users/{user['id']}/reset-password",
        json={"new_password": "Temp-9999", "must_change_password": True},
    )
    assert reset.status_code == 200

    admin_client.post("/api/auth/logout")
    assert (
        admin_client.post(
            "/api/auth/login", json={"login_id": "kim", "password": "Passw0rd!"}
        ).status_code
        == 401
    )
    me = admin_client.post(
        "/api/auth/login", json={"login_id": "kim", "password": "Temp-9999"}
    )
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True


def test_admin_cannot_disable_or_demote_themselves(admin_client):
    me = admin_client.get("/api/auth/me").json()
    assert (
        admin_client.patch(
            f"/api/users/{me['id']}", json={"is_active": False}
        ).status_code
        == 400
    )
    assert (
        admin_client.patch(f"/api/users/{me['id']}", json={"role": "user"}).status_code
        == 400
    )


def test_last_active_admin_cannot_be_demoted(admin_client, make_user):
    """Guard against locking every admin out of the system."""
    other = make_user("admin2", "관리자2", admin=True)
    me = admin_client.get("/api/auth/me").json()

    # Two admins: demoting the other one is fine.
    assert (
        admin_client.patch(f"/api/users/{other['id']}", json={"role": "user"}).status_code
        == 200
    )
    # Now only one admin remains -- and it is the caller, blocked by the
    # self-protection rule as well.
    assert (
        admin_client.patch(f"/api/users/{me['id']}", json={"role": "user"}).status_code
        == 400
    )


def test_user_creation_is_audited(admin_client):
    admin_client.post(
        "/api/users",
        json={"login_id": "hong", "display_name": "홍길동", "password": "Initial-123"},
    )
    logs = admin_client.get("/api/audit-logs", params={"action": "USER_CREATE"}).json()
    assert len(logs) == 1
    assert logs[0]["actor_display_name"] == "QA Admin"
    assert logs[0]["target_label"] == "홍길동(hong)"
    assert logs[0]["after_value"]["login_id"] == "hong"


def test_display_name_search_finds_korean_names(admin_client, make_user):
    make_user("hong", "홍길동")
    make_user("kim", "김철수")
    hits = admin_client.get("/api/users", params={"q": "홍길"}).json()
    assert [u["login_id"] for u in hits] == ["hong"]
