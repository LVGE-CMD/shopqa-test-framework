"""接口测试：认证。"""

from __future__ import annotations

import allure
import pytest

from framework.assertions import assert_json_contains, assert_schema, assert_status
from framework.data import load_yaml
from framework.db import fetch_one
from framework.schemas import ERROR_SCHEMA, LOGIN_SCHEMA, USER_SCHEMA
from tests.helpers import register_and_login

AUTH_CASES = load_yaml("api_cases.yaml")["auth"]

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("ShopLite 电商系统")
@allure.feature("认证")
class TestAuth:
    @allure.story("注册")
    @allure.title("注册成功，密码以哈希形式落库")
    @pytest.mark.smoke
    def test_register_success(self, api, db_path):
        response = api.post(
            "/api/auth/register",
            json={"username": "qa_register_ok", "password": "Passw0rd!"},
        )

        assert_status(response, 201)
        assert_schema(response.json(), USER_SCHEMA, "注册响应")
        assert response.json()["username"] == "qa_register_ok"

        row = fetch_one(
            db_path, "SELECT * FROM users WHERE username = ?", ("qa_register_ok",)
        )
        assert row is not None
        assert row["password_hash"] != "Passw0rd!"
        assert "$" in row["password_hash"]

    @allure.story("注册")
    @allure.title("用户名重复返回 400")
    def test_register_duplicate_username(self, api):
        payload = {"username": "qa_duplicate", "password": "Passw0rd!"}
        assert_status(api.post("/api/auth/register", json=payload), 201)

        response = api.post("/api/auth/register", json=payload)

        assert_status(response, 400)
        assert_schema(response.json(), ERROR_SCHEMA, "错误响应")
        assert_json_contains(response.json(), {"detail": "用户名已存在"})

    @allure.story("注册")
    @allure.title("非法注册参数返回 422：{case[title]}")
    @pytest.mark.parametrize(
        "case",
        AUTH_CASES["invalid_registrations"],
        ids=[item["case_id"] for item in AUTH_CASES["invalid_registrations"]],
    )
    def test_register_validation(self, api, case):
        response = api.post(
            "/api/auth/register",
            json={"username": case["username"], "password": case["password"]},
        )

        assert_status(response, case["expected_status"])

    @allure.story("登录")
    @allure.title("登录成功返回 token，并能用 token 获取当前用户")
    @pytest.mark.smoke
    def test_login_and_me(self, api, user):
        response = api.login(user["username"], user["password"])

        assert_status(response, 200)
        assert_schema(response.json(), LOGIN_SCHEMA, "登录响应")
        assert response.json()["token_type"] == "bearer"
        assert len(response.json()["access_token"]) >= 20

        me = api.get("/api/auth/me")
        assert_status(me, 200)
        assert_schema(me.json(), USER_SCHEMA, "当前用户")
        assert me.json()["username"] == user["username"]

    @allure.story("登录")
    @allure.title("密码错误返回 401")
    def test_login_wrong_password(self, api, user):
        response = api.post(
            "/api/auth/login",
            json={"username": user["username"], "password": "WrongPass1!"},
        )

        assert_status(response, 401)
        assert_json_contains(response.json(), {"detail": "用户名或密码错误"})

    @allure.story("鉴权")
    @allure.title("不带 token 访问受保护接口返回 401")
    def test_missing_token(self, api):
        response = api.get("/api/cart")

        assert_status(response, 401)
        assert_schema(response.json(), ERROR_SCHEMA, "401 响应")

    @allure.story("鉴权")
    @allure.title("伪造 token 返回 401")
    def test_invalid_token(self, api):
        api.set_token("this-is-not-a-real-token")

        assert_status(api.get("/api/cart"), 401)

    @allure.story("隔离")
    @allure.title("两个用户各自登录，token 不串号")
    def test_two_users_have_different_tokens(self, base_url, api, user):
        other, other_user = register_and_login(base_url)
        try:
            first_login = api.login(user["username"], user["password"])
            assert_status(first_login, 200)
            second_login = other.login(other_user["username"], other_user["password"])
            assert_status(second_login, 200)

            assert first_login.json()["access_token"] != second_login.json()["access_token"]
            assert api.get("/api/auth/me").json()["id"] == user["id"]
            assert other.get("/api/auth/me").json()["id"] == other_user["id"]
        finally:
            other.close()
