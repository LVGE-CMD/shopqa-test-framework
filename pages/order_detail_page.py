from __future__ import annotations

from os import name

import allure

from pages.base_page import BasePage


class OrderDetailPage(BasePage):
    path = "/orders"

    def is_success(self) -> bool:
        return self.is_visible("order-confirmation")

    def order_number(self) -> str:
        return self.text_of("order-number")

    def item_names(self) -> list[str]:
        return [
            item.inner_text().strip()
            for item in self.page.locator('[data-testid^="order-item-name-"]').all()
        ]

    def total(self) -> str:
        return self.text_of("order-total")

    def discount(self) -> str:
        return self.text_of("order-discount")

    def status(self) -> str:
        return self.text_of("order-status")

    @allure.step("打开全部订单")
    def view_all_orders(self):
        from pages.orders_page import OrdersPage

        self.locator("view-all-orders").click()
        self.wait_for_url("**/orders")
        return OrdersPage(self.page)
