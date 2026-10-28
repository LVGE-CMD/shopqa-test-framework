from __future__ import annotations

import allure

from pages.base_page import BasePage
from pages.order_detail_page import OrderDetailPage


class CheckoutPage(BasePage):
    path = "/checkout"

    def subtotal(self) -> str:
        return self.text_of("checkout-subtotal")

    @allure.step("使用优惠券{coupon_code}")
    def apply_coupon(self, coupon_code: str)->"CheckoutPage":
        self.locator("coupon-input").fill(coupon_code)
        return self


    @allure.step("提交订单")
    def place_order(self) -> OrderDetailPage:
        self.locator("place-order").click()
        self.wait_for_url("**/orders/*")
        return OrderDetailPage(self.page)

    def submit_expect_error(self) -> str:
        self.locator("place-order").click()
        self.page.wait_for_load_state("networkidle")
        self.expect_visible("flash-error")
        return self.text_of("flash-error")
