from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import get_settings


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    system_instruction: str
    temperature: float = 0.1
    max_output_tokens: int = 65536
    thinking_budget: int = 0


def _prompts_dir() -> Path:
    return get_settings().root / "app" / "prompts"


@lru_cache
def load_prompt(name: str) -> Prompt:
    path = _prompts_dir() / f"{name}.yaml"
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    generation = raw.get("generation", {})
    return Prompt(
        name=raw["name"],
        version=int(raw["version"]),
        system_instruction=raw["system_instruction"],
        temperature=float(generation.get("temperature", 0.1)),
        max_output_tokens=int(generation.get("max_output_tokens", 65536)),
        thinking_budget=int(generation.get("thinking_budget", 0)),
    )
