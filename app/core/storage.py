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
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, kind TEXT NOT NULL,
                    source TEXT NOT NULL, synced_at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS manual_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL,
                    manual_name TEXT NOT NULL, revision_label TEXT NOT NULL,
                    round_number INTEGER NOT NULL DEFAULT 0,
                    parent_revision_id INTEGER REFERENCES manual_revisions(id),
                    baseline_revision_id INTEGER REFERENCES manual_revisions(id),
                    source_path TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'REGISTERED',
                    analysis_id TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL REFERENCES manual_revisions(id),
                    kind TEXT NOT NULL, author TEXT, change_date TEXT, paragraph_index INTEGER,
                    text TEXT NOT NULL, functional INTEGER NOT NULL DEFAULT 1,
                    decision TEXT, confidence REAL, qa_decision TEXT, qa_note TEXT,
                    ai_judgment_json TEXT, source_page INTEGER, review_required INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, change_id INTEGER NOT NULL REFERENCES manual_changes(id),
                    round_number INTEGER NOT NULL DEFAULT 1, comment_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN', resolved_in_revision_id INTEGER REFERENCES manual_revisions(id),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_release_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER NOT NULL REFERENCES manual_revisions(id),
                    source TEXT NOT NULL, category TEXT, title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'MISSING_SUSPECTED',
                    matched_change_id INTEGER REFERENCES manual_changes(id),
                    created_at TEXT NOT NULL
                );
            """)
            # analyses는 기존 배포에 이미 존재할 수 있어 ADD COLUMN으로 안전하게 확장한다 (SQLite는 컬럼 추가만 지원).
            existing = {row["name"] for row in db.execute("PRAGMA table_info(analyses)")}
            for column, ddl in (
                ("stage", "TEXT"),
                ("stage_index", "INTEGER"),
                ("stage_total", "INTEGER"),
                ("started_at", "TEXT"),
                ("stage_updated_at", "TEXT"),
            ):
                if column not in existing:
                    db.execute(f"ALTER TABLE analyses ADD COLUMN {column} {ddl}")
            manual_change_columns = {row["name"] for row in db.execute("PRAGMA table_info(manual_changes)")}
            for column, ddl in (("source_page", "INTEGER"), ("review_required", "INTEGER NOT NULL DEFAULT 0")):
                if column not in manual_change_columns:
                    db.execute(f"ALTER TABLE manual_changes ADD COLUMN {column} {ddl}")
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

    def create_analysis(self, analysis_id: str, status: str = "QUEUED", stage_total: int = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO analyses(id,status,result_json,error,created_at,updated_at,stage,stage_index,stage_total,started_at,stage_updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (analysis_id, status, None, None, now, now, "대기 중", 0, stage_total, now, now),
            )

    def update_stage(self, analysis_id: str, index: int, name: str, stage_total: int | None = None) -> None:
        with self.connect() as db:
            if stage_total is None:
                db.execute(
                    "UPDATE analyses SET stage=?, stage_index=?, stage_updated_at=? WHERE id=?",
                    (name, index, datetime.now(timezone.utc).isoformat(), analysis_id),
                )
            else:
                db.execute(
                    "UPDATE analyses SET stage=?, stage_index=?, stage_total=?, stage_updated_at=? WHERE id=?",
                    (name, index, stage_total, datetime.now(timezone.utc).isoformat(), analysis_id),
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

    def sync_start(self, product: str, kind: str, source: str) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO sync_log(product,kind,source,synced_at,status,detail) VALUES(?,?,?,?,?,?)",
                (product, kind, source, datetime.now(timezone.utc).isoformat(), "RUNNING", ""),
            )
            return int(cursor.lastrowid)

    def sync_finish(self, sync_id: int, status: str, detail: str = "") -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE sync_log SET status=?, detail=?, synced_at=? WHERE id=?",
                (status, detail, datetime.now(timezone.utc).isoformat(), sync_id),
            )

    def is_sync_running(self, product: str, kind: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT status FROM sync_log WHERE product=? AND kind=? ORDER BY id DESC LIMIT 1", (product, kind)
            ).fetchone()
        return bool(row) and row["status"] == "RUNNING"

    def latest_sync(self, product: str, kind: str) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM sync_log WHERE product=? AND kind=? ORDER BY id DESC LIMIT 1", (product, kind)
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # manual_review: 매뉴얼 개정 검증 (Revision Lineage / Track Changes / QA Comment)
    # ------------------------------------------------------------------

    def add_manual_revision(
        self,
        product: str,
        manual_name: str,
        revision_label: str,
        source_path: Path,
        round_number: int = 0,
        parent_revision_id: int | None = None,
        baseline_revision_id: int | None = None,
        analysis_id: str | None = None,
        status: str = "REGISTERED",
    ) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO manual_revisions(product,manual_name,revision_label,round_number,parent_revision_id,baseline_revision_id,source_path,status,analysis_id,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (product, manual_name, revision_label, round_number, parent_revision_id, baseline_revision_id, str(source_path), status, analysis_id, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def get_manual_revision(self, revision_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM manual_revisions WHERE id=?", (revision_id,)).fetchone()
            return dict(row) if row else None

    def list_manual_revisions(self, product: str | None = None) -> list[dict]:
        with self.connect() as db:
            if product:
                rows = db.execute("SELECT * FROM manual_revisions WHERE product=? ORDER BY id DESC", (product,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM manual_revisions ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    def update_manual_revision_status(self, revision_id: int, status: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE manual_revisions SET status=? WHERE id=?", (status, revision_id))

    def add_manual_change(
        self,
        revision_id: int,
        kind: str,
        author: str,
        change_date: str,
        paragraph_index: int,
        text: str,
        functional: bool = True,
        source_page: int | None = None,
        review_required: bool = False,
    ) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO manual_changes(revision_id,kind,author,change_date,paragraph_index,text,functional,source_page,review_required,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (revision_id, kind, author, change_date, paragraph_index, text, int(functional), source_page, int(review_required), datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def update_manual_change_judgment(self, change_id: int, decision: str, confidence: float, ai_judgment: dict) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE manual_changes SET decision=?, confidence=?, ai_judgment_json=? WHERE id=?",
                (decision, confidence, json.dumps(ai_judgment, ensure_ascii=False), change_id),
            )

    def update_manual_change_qa_decision(self, change_id: int, qa_decision: str, qa_note: str = "") -> None:
        with self.connect() as db:
            db.execute("UPDATE manual_changes SET qa_decision=?, qa_note=? WHERE id=?", (qa_decision, qa_note, change_id))

    def get_manual_change(self, change_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM manual_changes WHERE id=?", (change_id,)).fetchone()
        if not row:
            return None
        value = dict(row)
        if value.get("ai_judgment_json"):
            value["ai_judgment"] = json.loads(value.pop("ai_judgment_json"))
        else:
            value["ai_judgment"] = None
            value.pop("ai_judgment_json", None)
        return value

    def list_manual_changes(self, revision_id: int) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM manual_changes WHERE revision_id=? ORDER BY paragraph_index, id", (revision_id,)).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            raw = value.pop("ai_judgment_json")
            value["ai_judgment"] = json.loads(raw) if raw else None
            values.append(value)
        return values

    def add_manual_comment(self, change_id: int, round_number: int, comment_text: str, status: str = "OPEN") -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO manual_comments(change_id,round_number,comment_text,status,created_at) VALUES(?,?,?,?,?)",
                (change_id, round_number, comment_text, status, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def update_manual_comment_status(self, comment_id: int, status: str, resolved_in_revision_id: int | None = None) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE manual_comments SET status=?, resolved_in_revision_id=? WHERE id=?",
                (status, resolved_in_revision_id, comment_id),
            )

    def get_manual_comment(self, comment_id: int) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT manual_comments.*, manual_changes.revision_id AS source_revision_id, "
                "manual_changes.text AS change_text FROM manual_comments "
                "JOIN manual_changes ON manual_changes.id=manual_comments.change_id "
                "WHERE manual_comments.id=?",
                (comment_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_open_comments_for_revision(self, revision_id: int) -> list[dict]:
        """revision_id와 그 조상 Round에서 아직 해결되지 않은 QA Comment 목록."""
        with self.connect() as db:
            lineage_ids: list[int] = []
            current_id: int | None = revision_id
            while current_id:
                lineage_ids.append(current_id)
                row = db.execute("SELECT parent_revision_id FROM manual_revisions WHERE id=?", (current_id,)).fetchone()
                current_id = row["parent_revision_id"] if row else None
            if not lineage_ids:
                return []
            placeholders = ",".join("?" for _ in lineage_ids)
            rows = db.execute(
                "SELECT manual_comments.*, manual_changes.text AS change_text FROM manual_comments "
                "JOIN manual_changes ON manual_changes.id = manual_comments.change_id "
                f"WHERE manual_changes.revision_id IN ({placeholders}) "
                "AND manual_comments.status IN ('OPEN','NOT_RESOLVED','REOPENED') ORDER BY manual_comments.id",
                lineage_ids,
            ).fetchall()
            return [dict(row) for row in rows]

    def add_release_finding(self, revision_id: int, source: str, category: str, title: str, status: str = "MISSING_SUSPECTED", matched_change_id: int | None = None) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO manual_release_findings(revision_id,source,category,title,status,matched_change_id,created_at) VALUES(?,?,?,?,?,?,?)",
                (revision_id, source, category, title, status, matched_change_id, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def list_release_findings(self, revision_id: int) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM manual_release_findings WHERE revision_id=? ORDER BY id", (revision_id,)).fetchall()
            return [dict(row) for row in rows]
