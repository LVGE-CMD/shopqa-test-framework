"""接口测试：商品查询。"""

from __future__ import annotations

import allure
import pytest

from framework.assertions import assert_schema, assert_status
from framework.data import load_yaml
from framework.schemas import PRODUCT_LIST_SCHEMA, PRODUCT_SCHEMA

SEARCH_CASES = load_yaml("product_cases.yaml")["search"]

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("商品")
class TestProducts:
    @allure.story("列表")
    @allure.title("商品列表返回 7 件商品，结构符合契约")
    def test_list_products(self, api):
        response = api.get("/api/products")

        assert_status(response, 200)
        body = response.json()
        assert_schema(body, PRODUCT_LIST_SCHEMA, "商品列表")
        assert body["total"] == len(body["items"])
        assert body["total"] == 7
        assert all(item["stock"] > 0 for item in body["items"])

    @allure.story("详情")
    @allure.title("按 ID 查询商品详情")
    def test_product_detail(self, api, products):
        target = products[0]

        response = api.get(f"/api/products/{target['id']}")

        assert_status(response, 200)
        assert_schema(response.json(), PRODUCT_SCHEMA, "商品详情")
        assert response.json()["name"] == target["name"]

    @allure.story("详情")
    @allure.title("查询不存在的商品返回 404")
    def test_product_not_found(self, api):
        response = api.get("/api/products/999999")

        assert_status(response, 404)
        assert response.json()["detail"] == "商品不存在"

    @allure.story("搜索")
    @allure.title("搜索 {case[case_id]}：{case[keyword]}")
    @pytest.mark.parametrize(
        "case", SEARCH_CASES, ids=[item["case_id"] for item in SEARCH_CASES]
    )
    def test_search_products(self, api, case):
        response = api.get("/api/products", params={"q": case["keyword"]})

        assert_status(response, 200)
        items = response.json()["items"]
        assert len(items) >= case["expected_min"]
        if case["should_find"]:
            assert case["should_find"] in [item["name"] for item in items]
        else:
            assert items == []

    @allure.story("搜索")
    @allure.title("搜索关键字不区分大小写")
    def test_search_is_case_insensitive(self, api):
        response = api.get("/api/products", params={"q": "USB"})

        assert_status(response, 200)
        assert [item["name"] for item in response.json()["items"]] == ["USB-C 扩展坞"]
