"""Web UI 自动化：登录。"""

from __future__ import annotations

import allure
import pytest

from pages.login_page import LoginPage
from pages.products_page import ProductsPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo123!"


@allure.epic("ShopLite 电商系统")
@allure.feature("Web UI - 登录")
class TestLogin:
    @allure.story("正常登录")
    @allure.title("演示账号可以登录并进入商品页")
    @pytest.mark.smoke
    def test_demo_user_login(self, page):
        login_page = LoginPage(page)
        login_page.goto()
        assert login_page.is_loaded()

        products_page = login_page.login(DEMO_USERNAME, DEMO_PASSWORD)
        products_page.wait_for_url("**/products*")

        assert products_page.is_loaded()
        assert products_page.text_of("current-user") == DEMO_USERNAME
        assert products_page.cart_count() == 0

    @allure.story("异常登录")
    @allure.title("密码错误时留在登录页并展示错误提示")
    def test_wrong_password_shows_error(self, page):
        login_page = LoginPage(page)
        login_page.goto()

        login_page.login(DEMO_USERNAME, "WrongPass1!")

        assert "/login" in page.url
        assert login_page.error_message() == "用户名或密码错误"
        assert login_page.is_loaded()

    @allure.story("访问控制")
    @allure.title("未登录访问订单页会被重定向到登录页")
    def test_protected_page_redirects_to_login(self, page):
        page.goto("/orders")

        page.wait_for_url("**/login*")
        assert "请先登录" in page.get_by_test_id("flash-error").inner_text()
        assert page.get_by_test_id("login-form").is_visible()

    @allure.story("退出")
    @allure.title("退出登录后再访问订单页需要重新登录")
    def test_logout_clears_session(self, page):
        login_page = LoginPage(page)
        login_page.goto()
        products_page = login_page.login(DEMO_USERNAME, DEMO_PASSWORD)
        products_page.wait_for_url("**/products*")

        products_page.locator("logout").click()
        products_page.wait_for_url("**/login*")

        page.goto("/orders")
        page.wait_for_url("**/login*")
        assert LoginPage(page).is_loaded()


@allure.epic("ShopLite 电商系统")
@allure.feature("Web UI - 商品")
class TestProductsPage:
    @allure.story("搜索")
    @allure.title("搜索“键盘”只展示匹配商品")
    def test_search_products(self, page):
        login_page = LoginPage(page)
        login_page.goto()
        products_page = login_page.login(DEMO_USERNAME, DEMO_PASSWORD)
        products_page.wait_for_url("**/products*")

        products_page.search("键盘")

        assert products_page.product_names() == ["机械键盘 Pro"]

    @allure.story("搜索")
    @allure.title("搜索不存在的商品展示空结果提示")
    def test_search_no_result(self, page):
        login_page = LoginPage(page)
        login_page.goto()
        products_page = login_page.login(DEMO_USERNAME, DEMO_PASSWORD)
        products_page.wait_for_url("**/products*")

        products_page.search("不存在的商品")

        message = products_page.no_product_message()
        assert "没有找到“不存在的商品”" in message
        assert products_page.product_names() == []


@allure.epic("ShopLite 电商系统")
@allure.feature("Web UI - 访问控制")
class TestProtectedPages:
    @allure.story("购物车")
    @allure.title("未登录访问购物车会被拦截")
    def test_cart_requires_login(self, page):
        page.goto("/cart")

        page.wait_for_url("**/login*")
        assert page.get_by_test_id("login-form").is_visible()
