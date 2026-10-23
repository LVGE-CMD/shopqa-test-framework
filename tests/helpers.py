from __future__ import annotations

import uuid

from framework.api_client import ApiClient
from framework.db import fetch_one


def product_by_name(products: list[dict], name: str) -> dict:
    for product in products:
        if product["name"] == name:
            return product
    raise AssertionError(f"找不到商品 {name}，当前商品：{[p['name'] for p in products]}")


def add_to_cart(api: ApiClient, product: dict, quantity: int = 1) -> None:
    response = api.post(
        "/api/cart/items",
        json={"product_id": product["id"], "quantity": quantity},
    )
    assert response.status_code == 200, response.text


def create_order(
    api: ApiClient,
    product: dict,
    quantity: int = 1,
    coupon: str | None = None,
):
    add_to_cart(api, product, quantity)
    payload = {"coupon_code": coupon} if coupon else {}
    return api.post("/api/orders", json=payload)


def register_and_login(base_url: str) -> tuple[ApiClient, dict]:
    client = ApiClient(base_url)
    username = f"qa_other_{uuid.uuid4().hex[:8]}"
    password = "Passw0rd!"
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201, response.text
    login = client.login(username, password)
    assert login.status_code == 200, login.text
    return client, {"id": response.json()["id"], "username": username, "password": password}


def stock_of(db_path, product_id: int) -> int:
    row = fetch_one(db_path, "SELECT stock FROM products WHERE id = ?", (product_id,))
    assert row is not None
    return int(row["stock"])
