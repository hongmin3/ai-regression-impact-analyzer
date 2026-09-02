"""Application settings.

All values come from environment variables (or /opt/qa-manual-hub/.env on the
server).  Nothing secret is ever hard-coded here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ALLOWED_EXTENSIONS = (
    "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,md,png,jpg,jpeg"
)


class Settings(BaseSettings):
    # Under systemd the values arrive via EnvironmentFile, so no file lookup is
    # needed.  The paths below are what makes ``python -m app.cli ...`` work
    # without ceremony: "../../.env" resolves to <APP_ROOT>/.env when the CLI is
    # run from <APP_ROOT>/app/backend, which is where the deploy layout puts it.
    # Later entries win, and a real environment variable always wins over both.
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- core ---
    app_name: str = "QA Manual Hub"
    environment: str = "production"
    debug: bool = False

    # --- database ---
    database_url: str = Field(
        default="postgresql+psycopg://qamanual:changeme@127.0.0.1:5432/qa_manual_hub"
    )

    # --- session / cookies ---
    session_cookie_name: str = "qamh_session"
    session_lifetime_hours: int = 8
    session_cookie_secure: bool = False  # flip to True once HTTPS is in front
    session_cookie_samesite: str = "lax"

    # --- storage ---
    storage_root: Path = Path("/srv/qa-manual-hub/storage")
    max_upload_mb: int = 500
    allowed_extensions: str = DEFAULT_ALLOWED_EXTENSIONS

    # --- office document preview (doc/docx/xls/xlsx/ppt/pptx -> PDF) ---
    # Converted PDFs are cached next to the original, so this only runs once
    # per uploaded file. Left as "soffice" on PATH; set an absolute path if the
    # server keeps LibreOffice somewhere non-standard.
    office_preview_binary: str = "soffice"
    office_preview_timeout_seconds: int = 90

    # --- password policy ---
    # 1 means "any non-empty password". Raise this in .env to enforce a minimum
    # without touching code; every check reads this value.
    password_min_length: int = 1

    # --- bootstrap (first-run admin creation only) ---
    bootstrap_admin_login_id: str | None = None
    bootstrap_admin_display_name: str | None = None
    bootstrap_admin_password: str | None = None

    # --- CORS (dev only; production is same-origin behind nginx) ---
    cors_origins: str = ""

    @field_validator("storage_root", mode="before")
    @classmethod
    def _expand(cls, v: object) -> object:
        if isinstance(v, str):
            return Path(v).expanduser()
        return v

    @property
    def allowed_extension_set(self) -> set[str]:
        return {
            e.strip().lower().lstrip(".")
            for e in self.allowed_extensions.split(",")
            if e.strip()
        }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
