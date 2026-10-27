from __future__ import annotations

from typing import TYPE_CHECKING

import allure
from playwright.sync_api import Locator, Page, expect

if TYPE_CHECKING:
    from playwright.sync_api import Page as PlaywrightPage


class BasePage:
    """所有页面对象的基类。

    这里用 Playwright 的 get_by_test_id，它默认查找 data-testid 属性。
    测试选择器跟着产品走，不依赖 CSS 样式和元素层级，页面改版时更稳。
    """

    path = "/"

    def __init__(self, page: Page):
        self.page = page

    def locator(self, test_id: str) -> Locator:
        return self.page.get_by_test_id(test_id)

    def goto(self) -> None:
        with allure.step(f"打开页面 {self.path}"):
            self.page.goto(self.path)

    def text_of(self, test_id: str) -> str:
        return self.locator(test_id).inner_text().strip()

    def is_visible(self, test_id: str) -> bool:
        return self.locator(test_id).is_visible()

    def expect_visible(self, test_id: str, timeout: int = 5000) -> None:
        expect(self.locator(test_id)).to_be_visible(timeout=timeout)

    def wait_for_url(self, pattern: str) -> None:
        self.page.wait_for_url(pattern)

    def screenshot(self, name: str = "screenshot") -> bytes:
        data = self.page.screenshot(full_page=True)
        allure.attach(data, name=name, attachment_type=allure.attachment_type.PNG)
        return data
