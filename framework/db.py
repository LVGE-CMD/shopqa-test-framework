from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Sequence


def _connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_one(db_path: Path | str, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    with _connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()


def fetch_all(db_path: Path | str, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    with _connect(db_path) as conn:
        return conn.execute(sql, params).fetchall()


def count(db_path: Path | str, table: str, where: str = "1=1", params: Sequence[Any] = ()) -> int:
    # table 只允许内部固定值，不接受外部输入。
    if table not in {"users", "products", "cart_items", "orders", "order_items", "tokens"}:
        raise ValueError(f"不允许查询的表：{table}")
    with _connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params).fetchone()
    return int(row["n"])
