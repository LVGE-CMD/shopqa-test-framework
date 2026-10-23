from __future__ import annotations

import json
import time
from typing import Any

import allure
import requests

from framework.logger import get_logger

logger = get_logger("shopqa.api")


def _safe_payload(payload: Any) -> Any:
    """日志和报告里不出现明文密码。"""
    if not isinstance(payload, dict):
        return payload
    hidden = {"password", "old_password", "new_password", "access_token", "token"}
    return {
        key: ("***" if key.lower() in hidden else _safe_payload(value))
        for key, value in payload.items()
    }


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


class ApiClient:
    """对 requests.Session 的薄封装。

    只做三件事：带 token、记录请求/响应、把结果挂到 Allure。
    业务断言留在测试用例里，客户端不替测试做判断。
    """

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.token: str | None = None

    def set_token(self, token: str) -> None:
        self.token = token
        self.session.headers["Authorization"] = f"Bearer {token}"

    def clear_token(self) -> None:
        self.token = None
        self.session.headers.pop("Authorization", None)

    def close(self) -> None:
        self.session.close()

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)
        with allure.step(f"{method.upper()} {path}"):
            started = time.perf_counter()
            response = self.session.request(method, url, **kwargs)
            elapsed_ms = (time.perf_counter() - started) * 1000

            request_body = kwargs.get("json") or kwargs.get("data")
            if request_body is not None:
                safe_request = _safe_payload(request_body)
                logger.info("request body: %s", safe_request)
                allure.attach(
                    _pretty(safe_request),
                    name="request body",
                    attachment_type=allure.attachment_type.JSON,
                )

            logger.info(
                "%s %s -> %s (%.0f ms)",
                method.upper(),
                path,
                response.status_code,
                elapsed_ms,
            )
            try:
                response_body = response.json()
                pretty_body = _pretty(response_body)
            except ValueError:
                pretty_body = response.text

            allure.attach(
                f"{method.upper()} {url}\nstatus={response.status_code}\n"
                f"elapsed={elapsed_ms:.0f} ms",
                name="request info",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                pretty_body,
                name=f"response {response.status_code}",
                attachment_type=allure.attachment_type.JSON,
            )
            return response

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    def login(self, username: str, password: str) -> requests.Response:
        response = self.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        if response.status_code == 200:
            self.set_token(response.json()["access_token"])
        return response
