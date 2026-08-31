from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.core.config import get_settings


class SpecificationSyncConfig(BaseModel):
    source: str = "manual"
    crawler_output_dir: str = ""
    filename_patterns: list[str] = Field(default_factory=list)


class TestCaseSyncConfig(BaseModel):
    source: str = "manual"


class SyncScheduleConfig(BaseModel):
    day_of_week: str = "*"
    schedule_time: str = "07:00"


class ProductConfig(BaseModel):
    product: str
    version: str = ""
    specification: SpecificationSyncConfig = Field(default_factory=SpecificationSyncConfig)
    testcase: TestCaseSyncConfig = Field(default_factory=TestCaseSyncConfig)
    sync: SyncScheduleConfig = Field(default_factory=SyncScheduleConfig)


def _products_dir(root: Path | None = None) -> Path:
    return (root or get_settings().root) / "config" / "products"


def load_product_config(name: str, root: Path | None = None) -> ProductConfig | None:
    path = _products_dir(root) / f"{name.lower()}.yaml"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return ProductConfig.model_validate(raw)


def list_product_configs(root: Path | None = None) -> list[ProductConfig]:
    directory = _products_dir(root)
    if not directory.is_dir():
        return []
    configs = []
    for path in sorted(directory.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        configs.append(ProductConfig.model_validate(raw))
    return configs
