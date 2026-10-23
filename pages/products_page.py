from __future__ import annotations

import allure

from pages.base_page import BasePage
from pages.cart_page import CartPage


class ProductsPage(BasePage):
    path = "/products"

    def is_loaded(self) -> bool:
        card = self.page.locator('[data-testid^="product-card-"]').first
        try:
            card.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def cart_count(self) -> int:
        text = self.text_of("cart-count")
        return int(text) if text else 0

    @allure.step("搜索商品：{keyword}")
    def search(self, keyword: str) -> "ProductsPage":
        self.locator("search-input").fill(keyword)
        self.locator("search-submit").click()
        self.page.wait_for_load_state("networkidle")
        return self

    def product_names(self) -> list[str]:
        return [
            item.inner_text().strip()
            for item in self.page.locator('[data-testid^="product-name-"]').all()
        ]

    @allure.step("把商品 {product_id} 加入购物车")
    def add_to_cart(self, product_id: int) -> CartPage:
        self.locator(f"add-to-cart-{product_id}").click()
        self.wait_for_url("**/cart*")
        return CartPage(self.page)

    def open_cart(self) -> CartPage:
        self.locator("nav-cart").click()
        self.wait_for_url("**/cart*")
        return CartPage(self.page)
