"""接口测试：订单、优惠券、数据库落库。"""

from __future__ import annotations

import allure
import pytest

from framework.assertions import assert_json_contains, assert_schema, assert_status
from framework.data import load_yaml
from framework.db import count, fetch_one
from framework.schemas import ERROR_SCHEMA, ORDER_LIST_SCHEMA, ORDER_SCHEMA
from tests.helpers import add_to_cart, create_order, register_and_login, stock_of

COUPON_CASES = load_yaml("api_cases.yaml")["coupons"]

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("订单")
class TestOrders:
    @allure.story("下单")
    @allure.title("下单成功：生成订单、扣减库存、清空购物车")
    @pytest.mark.smoke
    def test_create_order(self, auth_api, find_product, db_path, user):
        product = find_product("机械键盘 Pro")
        stock_before = stock_of(db_path, product["id"])

        response = create_order(auth_api, product, quantity=1)

        assert_status(response, 201)
        order = response.json()
        assert_schema(order, ORDER_SCHEMA, "订单")
        assert order["subtotal_cents"] == product["price_cents"]
        assert order["discount_cents"] == 0
        assert order["total_cents"] == product["price_cents"]
        assert order["status"] == "paid"
        assert order["order_no"].startswith("ORD-")

        assert auth_api.get("/api/cart").json()["items"] == []
        assert count(db_path, "orders", "user_id = ?", (user["id"],)) == 1
        assert count(db_path, "order_items", "order_id = ?", (order["id"],)) == 1
        assert stock_of(db_path, product["id"]) == stock_before - 1

    @allure.story("优惠券")
    @allure.title("优惠券 {case[case_id]}：{case[title]}")
    @pytest.mark.parametrize(
        "case", COUPON_CASES, ids=[item["case_id"] for item in COUPON_CASES]
    )
    def test_coupon_rules(self, auth_api, find_product, case):
        product = find_product(case["product_name"])
        add_to_cart(auth_api, product, case["quantity"])

        response = auth_api.post(
            "/api/orders", json={"coupon_code": case["coupon"]}
        )

        assert_status(response, case["expected_status"])
        if case["expected_status"] == 201:
            order = response.json()
            assert_schema(order, ORDER_SCHEMA, "订单")
            assert order["discount_cents"] == case["expected_discount_cents"]
            assert order["total_cents"] == order["subtotal_cents"] - order["discount_cents"]
        else:
            assert_json_contains(response.json(), {"detail": case["expected_detail"]})
            # 下单失败不能清空购物车，用户可以改数量/改券后重试。
            cart = auth_api.get("/api/cart")
            assert cart.json()["total_quantity"] == case["quantity"]

    @allure.story("下单")
    @allure.title("购物车为空时下单返回 400")
    def test_checkout_empty_cart(self, auth_api):
        response = auth_api.post("/api/orders", json={})

        assert_status(response, 400)
        assert response.json()["detail"] == "购物车为空，不能结算"

    @allure.story("订单列表")
    @allure.title("订单列表按最新订单倒序返回")
    def test_order_list(self, auth_api, find_product):
        keyboard = find_product("机械键盘 Pro")
        mouse = find_product("无线鼠标 Lite")
        first = create_order(auth_api, keyboard, 1).json()
        second = create_order(auth_api, mouse, 1).json()

        response = auth_api.get("/api/orders")

        assert_status(response, 200)
        assert_schema(response.json(), ORDER_LIST_SCHEMA, "订单列表")
        assert response.json()["total"] == 2
        assert [item["id"] for item in response.json()["items"]] == [
            second["id"],
            first["id"],
        ]

    @allure.story("订单详情")
    @allure.title("订单详情包含商品快照")
    def test_order_detail(self, auth_api, find_product):
        product = find_product("超大桌垫")
        order = create_order(auth_api, product, 2).json()

        response = auth_api.get(f"/api/orders/{order['id']}")

        assert_status(response, 200)
        body = response.json()
        assert_schema(body, ORDER_SCHEMA, "订单详情")
        assert body["items"][0]["product_id"] == product["id"]
        assert body["items"][0]["quantity"] == 2
        assert body["items"][0]["line_total_cents"] == product["price_cents"] * 2

    @allure.story("订单详情")
    @allure.title("查询别人的订单返回 404")
    def test_order_is_isolated_between_users(self, base_url, auth_api, find_product, user):
        product = find_product("机械键盘 Pro")
        order = create_order(auth_api, product, 1).json()

        other, other_user = register_and_login(base_url)
        try:
            response = other.get(f"/api/orders/{order['id']}")
            assert_status(response, 404)
            assert response.json()["detail"] == "订单不存在"

            assert other.get("/api/orders").json()["total"] == 0
            assert auth_api.get("/api/orders").json()["total"] == 1
        finally:
            other.close()

    @allure.story("鉴权")
    @allure.title("未登录不能创建订单")
    def test_create_order_requires_login(self, api, find_product):
        product = find_product("机械键盘 Pro")
        response = api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )
        assert_status(response, 401)

        assert_status(api.post("/api/orders", json={}), 401)
        assert_schema(api.post("/api/orders", json={}).json(), ERROR_SCHEMA, "401 响应")

    @allure.story("库存")
    @allure.title("订单写入后库存不能变成负数")
    def test_stock_never_negative(self, auth_api, find_product, db_path):
        product = find_product("高清摄像头")
        stock_before = stock_of(db_path, product["id"])

        response = create_order(auth_api, product, min(3, stock_before))

        assert_status(response, 201)
        after = stock_of(db_path, product["id"])
        assert after == stock_before - min(3, stock_before)
        assert after >= 0
