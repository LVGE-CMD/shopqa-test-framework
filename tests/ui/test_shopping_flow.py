"""Web UI 自动化：从登录到下单的完整链路。"""

from __future__ import annotations

import allure
import pytest

from framework.db import count, fetch_one
from pages.cart_page import CartPage
from pages.login_page import LoginPage
from pages.orders_page import OrdersPage
from pages.products_page import ProductsPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("Web UI - 购物流程")
class TestShoppingFlow:
    @allure.story("主流程")
    @allure.title("登录 → 加购 → 结算 → 下单成功")
    @pytest.mark.smoke
    def test_login_add_to_cart_and_checkout(
        self, page, login_as, find_product, db_path, user
    ):
        product = find_product("机械键盘 Pro")
        products_page = login_as()
        products_page.wait_for_url("**/products*")

        cart_page = products_page.add_to_cart(product["id"])

        assert cart_page.quantity_of(product["id"]) == "1"
        assert cart_page.subtotal() == "¥89.00"

        checkout_page = cart_page.go_to_checkout()
        assert checkout_page.subtotal() == "¥89.00"
        order_page = checkout_page.place_order()

        assert order_page.is_success()
        order_no = order_page.order_number()
        assert order_no.startswith("ORD-")
        assert order_page.total() == "¥89.00"
        assert order_page.status() == "paid"

        order_row = fetch_one(db_path, "SELECT * FROM orders WHERE order_no = ?", (order_no,))
        assert order_row is not None
        assert order_row["user_id"] == user["id"]
        assert count(db_path, "order_items", "order_id = ?", (order_row["id"],)) == 1

    @allure.story("购物车")
    @allure.title("修改数量后小计更新，移除后购物车为空")
    def test_update_quantity_and_remove(self, page, login_as, find_product):
        product = find_product("无线鼠标 Lite")
        products_page = login_as()
        products_page.wait_for_url("**/products*")
        cart_page = products_page.add_to_cart(product["id"])

        cart_page.update_quantity(product["id"], 2)

        assert cart_page.quantity_of(product["id"]) == "2"
        assert cart_page.subtotal() == "¥78.00"

        cart_page.remove(product["id"])
        assert cart_page.is_empty()

    @allure.story("优惠券")
    @allure.title("购物车满 100 元时 QA10 优惠 10%")
    def test_coupon_at_threshold(self, page, login_as, find_product):
        product = find_product("超大桌垫")
        products_page = login_as()
        products_page.wait_for_url("**/products*")

        products_page.add_to_cart(product["id"])
        page.goto("/products")
        products_page = ProductsPage(page)
        cart_page = products_page.add_to_cart(product["id"])

        assert cart_page.subtotal() == "¥100.00"
        checkout_page = cart_page.go_to_checkout()
        order_page = checkout_page.place_order("QA10")

        assert order_page.is_success()
        assert order_page.discount() == "- ¥10.00"
        assert order_page.total() == "¥90.00"

    @allure.story("优惠券")
    @allure.title("购物车不满 100 元时 QA10 被拒绝")
    def test_coupon_below_threshold(self, page, login_as, find_product):
        product = find_product("无线鼠标 Lite")
        products_page = login_as()
        products_page.wait_for_url("**/products*")
        cart_page = products_page.add_to_cart(product["id"])

        checkout_page = cart_page.go_to_checkout()
        error = checkout_page.submit_expect_error("QA10")

        assert "优惠券 QA10 需满" in error
        assert "/checkout" in page.url
        assert page.get_by_test_id("cart-count").inner_text() == "1"

    @allure.story("空购物车")
    @allure.title("购物车为空时访问结算页会被送回购物车")
    def test_empty_cart_cannot_checkout(self, page, login_as):
        products_page = login_as()
        products_page.wait_for_url("**/products*")

        page.goto("/checkout")

        page.wait_for_url("**/cart*")
        assert "购物车为空" in page.get_by_test_id("flash-error").inner_text()
        assert CartPage(page).is_empty()

    @allure.story("订单")
    @allure.title("下单后可以在订单列表和订单详情中看到订单")
    def test_order_is_visible_in_history(self, page, login_as, find_product):
        product = find_product("笔记本内胆包")
        products_page = login_as()
        products_page.wait_for_url("**/products*")
        cart_page = products_page.add_to_cart(product["id"])
        order_page = cart_page.go_to_checkout().place_order()
        order_no = order_page.order_number()

        orders_page = OrdersPage(page)
        orders_page.goto()

        assert orders_page.has_order(order_no)
        detail = orders_page.open_order(order_no)
        assert detail.order_number() == order_no
        assert detail.total() == "¥29.00"
