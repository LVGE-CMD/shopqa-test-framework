"""ShopLite 的 SQLite 数据层。

被测系统故意做得小而完整：用户、商品、购物车、订单、库存、优惠券
都在一个 SQLite 文件里，测试可以同时做接口断言和数据库断言。
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(
    os.getenv("SHOPLITE_DB_PATH", str(Path(__file__).resolve().parent / "shoplite.db"))
)

# 价格统一用“分”存整数，避免浮点数 0.1 + 0.2 这类精度问题。
SEED_PRODUCTS = [
    {
        "name": "机械键盘 Pro",
        "description": "87 键热插拔，适合写代码和写测试用例。",
        "price_cents": 8900,
        "stock": 12,
        "emoji": "⌨️",
    },
    {
        "name": "无线鼠标 Lite",
        "description": "轻量办公鼠标，静音微动，续航 6 个月。",
        "price_cents": 3900,
        "stock": 25,
        "emoji": "🖱️",
    },
    {
        "name": "USB-C 扩展坞",
        "description": "HDMI + USB 3.0 + 读卡器，一根线扩展桌面。",
        "price_cents": 5900,
        "stock": 18,
        "emoji": "🔌",
    },
    {
        "name": "显示器支架",
        "description": "铝合金悬臂，支持 17-32 英寸显示器。",
        "price_cents": 4500,
        "stock": 10,
        "emoji": "🖥️",
    },
    {
        "name": "高清摄像头",
        "description": "1080P 自动对焦，线上面试和开会在家用。",
        "price_cents": 7900,
        "stock": 8,
        "emoji": "📷",
    },
    {
        "name": "笔记本内胆包",
        "description": "防泼水面料，14 英寸笔记本刚好放下。",
        "price_cents": 2900,
        "stock": 40,
        "emoji": "🎒",
    },
    {
        "name": "超大桌垫",
        "description": "90×40cm，键盘鼠标一起放，桌面更整齐。",
        "price_cents": 5000,
        "stock": 30,
        "emoji": "🟫",
    },
]

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo123!"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()
    return secrets.compare_digest(actual, expected)


def token_digest(token: str) -> str:
    """数据库只存 token 的哈希，即使库泄露也不能直接拿来登录。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                stock INTEGER NOT NULL CHECK (stock >= 0),
                emoji TEXT NOT NULL DEFAULT '📦',
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                subtotal_cents INTEGER NOT NULL,
                discount_cents INTEGER NOT NULL DEFAULT 0,
                total_cents INTEGER NOT NULL,
                coupon_code TEXT,
                status TEXT NOT NULL DEFAULT 'paid',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                unit_price_cents INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                line_total_cents INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );
            """
        )


def seed() -> None:
    """第一次启动时写入商品和演示账号，重复启动不会重复插入。"""
    with db() as conn:
        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            conn.executemany(
                """
                INSERT INTO products (name, description, price_cents, stock, emoji)
                VALUES (:name, :description, :price_cents, :stock, :emoji)
                """,
                SEED_PRODUCTS,
            )

        user_count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?", (DEMO_USERNAME,)
        ).fetchone()[0]
        if user_count == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (DEMO_USERNAME, hash_password(DEMO_PASSWORD)),
            )
