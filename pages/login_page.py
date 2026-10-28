from __future__ import annotations

import allure

from pages.base_page import BasePage
from pages.products_page import ProductsPage


class LoginPage(BasePage):
    path = "/login"

    @allure.step("用账号 {username} 登录")
    def login(self, username: str, password: str) -> ProductsPage:
        self.locator("login-username").fill(username)
        self.locator("login-password").fill(password)
        self.locator("login-submit").click()
        self.page.wait_for_load_state("networkidle")
        return ProductsPage(self.page)

    @allure.step("使用错误密码登录: {username}")
    def login_expect_error(self,username:str,password:str)->str:
        self.locator("login-username").fill(username)
        self.locator("login-password").fill(password)
        self.locator("login-submit").click()
        self.page.wait_for_load_state("networkidle")
        self.expect_visible("flash-error")
        return self.error_message()

    def error_message(self) -> str:
        return self.text_of("flash-error")

    def is_loaded(self) -> bool:
        return self.is_visible("login-form")
