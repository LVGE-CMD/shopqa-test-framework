from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass(frozen=True)
class Settings:
    browser: str = field(default_factory=lambda: os.getenv("SHOPLITE_BROWSER", "msedge"))
    headless: bool = field(
        default_factory=lambda: _as_bool(os.getenv("SHOPLITE_HEADLESS"), True)
    )
    timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("SHOPLITE_TIMEOUT_MS", "10000"))
    )
    base_url: str | None = field(default_factory=lambda: os.getenv("SHOPLITE_BASE_URL"))
    db_path: str | None = field(default_factory=lambda: os.getenv("SHOPLITE_DB_PATH"))
    slow_mo: int = field(
        default_factory=lambda: int(os.getenv("SHOPLITE_SLOW_MO", "0"))
    )


def get_settings() -> Settings:
    return Settings()
