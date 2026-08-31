from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    app_secret_key: str = ""


class Settings(BaseModel):
    raw: dict[str, Any]
    secrets: Secrets
    root: Path = ROOT

    def get(self, dotted: str, default: Any = None) -> Any:
        value: Any = self.raw
        for key in dotted.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def path(self, dotted: str) -> Path:
        return self.root / str(self.get(dotted))


@lru_cache
def get_settings() -> Settings:
    with (ROOT / "config.yaml").open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    settings = Settings(raw=raw, secrets=Secrets())
    for key in ("upload_dir", "specification_dir", "testcase_dir", "index_dir"):
        settings.path(f"storage.{key}").mkdir(parents=True, exist_ok=True)
    for key in ("report_dir", "export_dir", "log_dir"):
        settings.path(f"storage.{key}").mkdir(parents=True, exist_ok=True)
    return settings
