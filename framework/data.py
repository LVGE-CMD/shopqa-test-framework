from __future__ import annotations

from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_yaml(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"测试数据文件不存在：{path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
