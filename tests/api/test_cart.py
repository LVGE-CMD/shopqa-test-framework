"""接口测试：购物车。"""

from __future__ import annotations

import allure
import pytest

from framework.api_client import ApiClient
from framework.assertions import assert_schema, assert_status
from framework.db import count
from framework.schemas import CART_SCHEMA, ERROR_SCHEMA
from tests.helpers import register_and_login

INVALID_QUANTITIES = [0, -1, 100]

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("购物车")
class TestCart:
    @allure.story("加入")
    @allure.title("加入购物车后金额计算正确")
    @pytest.mark.smoke
    def test_add_to_cart(self, auth_api, find_product, db_path, user):
        product = find_product("机械键盘 Pro")

        response = auth_api.post(
            "/api/cart/items",
            json={"product_id": product["id"], "quantity": 2},
        )

        assert_status(response, 200)
        cart = response.json()
        assert_schema(cart, CART_SCHEMA, "购物车")
        assert cart["total_quantity"] == 2
        assert cart["subtotal_cents"] == product["price_cents"] * 2
        assert cart["items"][0]["line_total_cents"] == product["price_cents"] * 2
        assert count(db_path, "cart_items", "user_id = ?", (user["id"],)) == 1

    @allure.story("加入")
    @allure.title("重复加入同一商品会累加数量")
    def test_add_same_product_twice(self, auth_api, find_product):
        product = find_product("无线鼠标 Lite")

        auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )
        response = auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 2}
        )

        assert_status(response, 200)
        assert response.json()["total_quantity"] == 3
        assert len(response.json()["items"]) == 1

    @allure.story("库存")
    @allure.title("加入数量超过库存返回 400")
    def test_add_over_stock(self, auth_api, find_product):
        product = find_product("高清摄像头")

        response = auth_api.post(
            "/api/cart/items",
            json={"product_id": product["id"], "quantity": product["stock"] + 1},
        )

        assert_status(response, 400)
        assert "库存不足" in response.json()["detail"]

    @allure.story("修改")
    @allure.title("修改购物车数量")
    def test_update_quantity(self, auth_api, find_product):
        product = find_product("USB-C 扩展坞")
        auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )

        response = auth_api.patch(
            f"/api/cart/items/{product['id']}", json={"quantity": 4}
        )

        assert_status(response, 200)
        assert response.json()["total_quantity"] == 4
        assert response.json()["subtotal_cents"] == product["price_cents"] * 4

    @allure.story("库存")
    @allure.title("修改数量超过库存返回 400")
    def test_update_over_stock(self, auth_api, find_product):
        product = find_product("显示器支架")
        auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )

        response = auth_api.patch(
            f"/api/cart/items/{product['id']}",
            json={"quantity": product["stock"] + 1},
        )

        assert_status(response, 400)
        assert "库存不足" in response.json()["detail"]

    @allure.story("删除")
    @allure.title("删除购物车商品后列表为空")
    def test_remove_item(self, auth_api, find_product):
        product = find_product("笔记本内胆包")
        auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )

        assert_status(auth_api.delete(f"/api/cart/items/{product['id']}"), 204)

        cart = auth_api.get("/api/cart")
        assert_status(cart, 200)
        assert cart.json()["items"] == []
        assert cart.json()["subtotal_cents"] == 0

    @allure.story("删除")
    @allure.title("删除不存在的购物车商品返回 404")
    def test_remove_missing_item(self, auth_api):
        response = auth_api.delete("/api/cart/items/999999")

        assert_status(response, 404)
        assert response.json()["detail"] == "购物车里没有这件商品"

    @allure.story("校验")
    @allure.title("非法购买数量返回 422：{quantity}")
    @pytest.mark.parametrize("quantity", INVALID_QUANTITIES)
    def test_invalid_quantity(self, auth_api, find_product, quantity):
        product = find_product("机械键盘 Pro")

        response = auth_api.post(
            "/api/cart/items",
            json={"product_id": product["id"], "quantity": quantity},
        )

        assert_status(response, 422)
        assert_schema(response.json(), {"type": "object", "required": ["detail"]})

    @allure.story("商品")
    @allure.title("加入不存在的商品返回 404")
    def test_add_missing_product(self, auth_api):
        response = auth_api.post(
            "/api/cart/items", json={"product_id": 999999, "quantity": 1}
        )

        assert_status(response, 404)
        assert response.json()["detail"] == "商品不存在或已下架"

    @allure.story("鉴权")
    @allure.title("未登录不能加入购物车")
    def test_add_requires_login(self, api, find_product):
        product = find_product("机械键盘 Pro")

        response = api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 1}
        )

        assert_status(response, 401)
        assert_schema(response.json(), ERROR_SCHEMA, "401 响应")

    @allure.story("隔离")
    @allure.title("用户只能看到自己的购物车")
    def test_cart_is_isolated_between_users(self, base_url, auth_api, find_product, user):
        product = find_product("机械键盘 Pro")
        auth_api.post(
            "/api/cart/items", json={"product_id": product["id"], "quantity": 2}
        )

        other, other_user = register_and_login(base_url)
        try:
            other_cart = other.get("/api/cart")
            assert_status(other_cart, 200)
            assert other_cart.json()["items"] == []

            my_cart = auth_api.get("/api/cart")
            assert my_cart.json()["total_quantity"] == 2
        finally:
            other.close()
