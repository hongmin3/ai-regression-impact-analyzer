from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


class Storage:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (get_settings().root / "data" / "app.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    DEFAULT_PRODUCTS = ("VXvue", "Bellalun Viewer")

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    product TEXT NOT NULL, version TEXT, revision TEXT,
                    name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
                    metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, result_json TEXT,
                    error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_cache (
                    cache_key TEXT PRIMARY KEY, response_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS product_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, version TEXT NOT NULL,
                    created_at TEXT NOT NULL, UNIQUE(product, version)
                );
            """)
            now = datetime.now(timezone.utc).isoformat()
            for name in self.DEFAULT_PRODUCTS:
                db.execute("INSERT OR IGNORE INTO products(name,created_at) VALUES(?,?)", (name, now))

    def list_products(self) -> list[str]:
        with self.connect() as db:
            return [row["name"] for row in db.execute("SELECT name FROM products ORDER BY name")]

    def ensure_product(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO products(name,created_at) VALUES(?,?)", (name, datetime.now(timezone.utc).isoformat()))

    def list_versions(self, product: str) -> list[str]:
        with self.connect() as db:
            return [row["version"] for row in db.execute("SELECT version FROM product_versions WHERE product=? ORDER BY version", (product,))]

    def ensure_version(self, product: str, version: str) -> None:
        version = version.strip()
        if not version:
            return
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO product_versions(product,version,created_at) VALUES(?,?,?)",
                (product, version, datetime.now(timezone.utc).isoformat()),
            )

    def active_documents(self, kind: str, product: str) -> list[dict]:
        """제품에 등록된 모든 문서를 반환한다.

        사양서1~5처럼 서로 다른 문서가 같은 제품·버전 아래 여러 개 등록될 수 있으므로,
        새 문서가 추가돼도 이전 문서를 검색 대상에서 제외(레거시 처리)하지 않고 전부 포함한다.
        """
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM documents WHERE kind=? AND product=? ORDER BY id", (kind, product)
            ).fetchall()
        return [dict(row) for row in rows]

    def add_document(self, kind: str, product: str, version: str, revision: str, name: str, path: Path, metadata: dict | None = None) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO documents(kind,product,version,revision,name,path,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (kind, product, version, revision, name, str(path), json.dumps(metadata or {}, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def list_documents(self, kind: str) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM documents WHERE kind=? ORDER BY id DESC", (kind,))]

    def get_document(self, document_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            return dict(row) if row else None

    def delete_document(self, document_id: int) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def create_analysis(self, analysis_id: str, status: str = "QUEUED") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO analyses(id,status,result_json,error,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (analysis_id, status, None, None, now, now),
            )

    def update_analysis(self, analysis_id: str, status: str, result: dict | None = None, error: str | None = None) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE analyses SET status=?,result_json=?,error=?,updated_at=? WHERE id=?",
                (status, json.dumps(result, ensure_ascii=False) if result is not None else None, error, datetime.now(timezone.utc).isoformat(), analysis_id),
            )

    def get_analysis(self, analysis_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if not row:
            return None
        value = dict(row)
        if value["result_json"]:
            value["result"] = json.loads(value.pop("result_json"))
        else:
            value.pop("result_json")
        return value

    def list_analyses(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            raw = value.pop("result_json")
            value["result"] = json.loads(raw) if raw else None
            values.append(value)
        return values

    def tokens_used_since(self, since_iso: str) -> int:
        """지정 시각 이후 완료된 분석의 total_tokens 합계. 한도 체크용이라 대략치면 충분하다."""
        with self.connect() as db:
            rows = db.execute(
                "SELECT result_json FROM analyses WHERE status='DONE' AND created_at>=? AND result_json IS NOT NULL",
                (since_iso,),
            ).fetchall()
        total = 0
        for row in rows:
            try:
                total += int(json.loads(row["result_json"]).get("token_usage", {}).get("total_tokens", 0))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return total

    def fail_incomplete_analyses(self, error: str = "서버 재시작으로 분석이 중단되었습니다.") -> int:
        """A process restart cannot resume in-memory BackgroundTasks safely."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE analyses SET status='FAILED',error=?,updated_at=? WHERE status IN ('QUEUED','RUNNING')",
                (error, now),
            )
            return cursor.rowcount

    def cache_get(self, key: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT response_json FROM ai_cache WHERE cache_key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def cache_set(self, key: str, value: dict) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO ai_cache VALUES(?,?,?)", (key, json.dumps(value, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
