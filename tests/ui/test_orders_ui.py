"""Web UI 自动化：订单隔离。"""

from __future__ import annotations

import allure
import pytest

from pages.login_page import LoginPage
from pages.orders_page import OrdersPage
from tests.helpers import create_order

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("Web UI - 订单")
class TestOrderIsolation:
    @allure.story("订单详情")
    @allure.title("直接改 URL 也看不到别人的订单")
    def test_cannot_open_another_users_order(
        self, page, auth_api, user, find_product, user_factory
    ):
        product = find_product("机械键盘 Pro")
        order = create_order(auth_api, product, 1).json()

        other = user_factory()
        login_page = LoginPage(page)
        login_page.goto()
        products_page = login_page.login(other["username"], other["password"])
        products_page.wait_for_url("**/products*")

        orders_page = OrdersPage(page)
        orders_page.goto()
        assert orders_page.is_empty()

        page.goto(f"/orders/{order['id']}")

        page.wait_for_url("**/orders*")
        assert "订单不存在" in page.get_by_test_id("flash-error").inner_text()
