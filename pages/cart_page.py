from __future__ import annotations

import allure

from pages.base_page import BasePage
from pages.checkout_page import CheckoutPage


class CartPage(BasePage):
    path = "/cart"

    def is_empty(self) -> bool:
        return self.is_visible("cart-empty")

    def subtotal(self) -> str:
        return self.text_of("cart-subtotal")

    def quantity_of(self, product_id: int) -> str:
        return self.locator(f"cart-qty-{product_id}").input_value()

    def line_total(self, product_id: int) -> str:
        return self.text_of(f"cart-line-total-{product_id}")

    @allure.step("把商品 {product_id} 的数量改成 {quantity}")
    def update_quantity(self, product_id: int, quantity: int) -> "CartPage":
        self.locator(f"cart-qty-{product_id}").fill(str(quantity))
        self.locator(f"update-qty-{product_id}").click()
        self.page.wait_for_load_state("networkidle")
        return self

    @allure.step("把商品{product_id}的数量改成{quantity}，预期失败")
    def update_quantity_expect_error(self, product_id: int, quantity: int) -> str:
        self.locator(f"cart-qty-{product_id}").fill(str(quantity))
        self.locator(f"cart-qty-{product_id}").evaluate("el => el.form.submit()")
        self.page.wait_for_load_state("networkidle")
        self.expect_visible("flash-error")
        return self.text_of("flash-error")


    @allure.step("从购物车移除商品 {product_id}")
    def remove(self, product_id: int) -> "CartPage":
        self.locator(f"remove-item-{product_id}").click()
        self.page.wait_for_load_state("networkidle")
        return self

    @allure.step("进入结算页")
    def go_to_checkout(self) -> CheckoutPage:
        self.locator("go-checkout").click()
        self.wait_for_url("**/checkout*")
        return CheckoutPage(self.page)
