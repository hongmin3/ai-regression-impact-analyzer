"""Test fixtures.

The suite runs against a real PostgreSQL database because the schema relies on
PostgreSQL features (JSONB, functional unique indexes, ``FOR UPDATE``).  Point
``TEST_DATABASE_URL`` at a throw-away database; the schema is created and dropped
around the session.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://qamanual:qamanual@127.0.0.1:5432/qa_manual_hub_test",
    ),
)


@pytest.fixture(scope="session")
def storage_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("qamh-storage")
    os.environ["STORAGE_ROOT"] = str(root)
    return root


@pytest.fixture(scope="session")
def app_settings(storage_root: Path):
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.storage_root = storage_root
    return settings


@pytest.fixture(scope="session")
def engine(app_settings):
    from app.db import Base, engine as app_engine
    from app import models  # noqa: F401

    Base.metadata.drop_all(app_engine)
    Base.metadata.create_all(app_engine)
    yield app_engine
    Base.metadata.drop_all(app_engine)


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """Truncate between tests so each one starts from an empty database."""
    from sqlalchemy import text

    from app.db import Base

    yield
    names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(engine, app_settings) -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(engine):
    """Create a user directly, bypassing HTTP, for arranging test state."""
    from app.db import SessionLocal
    from app.models import ROLE_ADMIN, ROLE_USER, User
    from app.security import hash_password

    created: list[uuid.UUID] = []

    def _make(
        login_id: str,
        display_name: str,
        password: str = "Passw0rd!",
        *,
        admin: bool = False,
        is_active: bool = True,
        must_change_password: bool = False,
    ) -> dict:
        with SessionLocal() as db:
            user = User(
                login_id=login_id,
                display_name=display_name,
                password_hash=hash_password(password),
                role=ROLE_ADMIN if admin else ROLE_USER,
                is_active=is_active,
                must_change_password=must_change_password,
            )
            db.add(user)
            db.commit()
            created.append(user.id)
            return {
                "id": str(user.id),
                "login_id": login_id,
                "display_name": display_name,
                "password": password,
            }

    return _make


@pytest.fixture
def login(client):
    def _login(login_id: str, password: str = "Passw0rd!"):
        response = client.post(
            "/api/auth/login", json={"login_id": login_id, "password": password}
        )
        return response

    return _login


@pytest.fixture
def admin_client(client, make_user, login):
    make_user("admin", "QA Admin", admin=True)
    assert login("admin").status_code == 200
    return client


@pytest.fixture
def catalog(admin_client):
    """One product plus one category, created through the API as an admin."""
    product = admin_client.post(
        "/api/products", json={"name": "Bellalun Viewer", "code": "BLV"}
    )
    assert product.status_code == 201, product.text
    category = admin_client.post("/api/categories", json={"name": "Operation Manual"})
    assert category.status_code == 201, category.text
    return {"product": product.json(), "category": category.json()}


@pytest.fixture
def pdf_bytes():
    def _make(marker: str = "v1") -> bytes:
        # Minimal but real PDF header so the magic-number check passes.
        return b"%PDF-1.7\n%%marker:" + marker.encode() + b"\n%%EOF\n"

    return _make
