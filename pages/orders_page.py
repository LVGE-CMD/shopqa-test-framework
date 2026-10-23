from __future__ import annotations

import allure

from pages.base_page import BasePage


class OrdersPage(BasePage):
    path = "/orders"

    def is_empty(self) -> bool:
        return self.is_visible("orders-empty")

    def has_order(self, order_no: str) -> bool:
        row = self.page.locator('[data-testid^="order-no-"]').filter(has_text=order_no)
        try:
            row.first.wait_for(state="visible", timeout=5000)
        except Exception:
            return False
        return row.count() >= 1

    @allure.step("打开订单号包含 {order_no} 的订单")
    def open_order(self, order_no: str):
        from pages.order_detail_page import OrderDetailPage

        row = self.page.locator('[data-testid^="order-row-"]').filter(has_text=order_no)
        row.first.get_by_text("查看").click()
        self.wait_for_url("**/orders/*")
        return OrderDetailPage(self.page)
