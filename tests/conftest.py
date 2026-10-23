from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import allure
import pytest
import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.api_client import ApiClient
from framework.config import get_settings
from framework.logger import setup_logging

setup_logging()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def demo_server():
    """启动被测服务；如果设置了 SHOPLITE_BASE_URL，则直接测已有环境。"""
    external = os.getenv("SHOPLITE_BASE_URL")
    if external:
        external_db = os.getenv("SHOPLITE_DB_PATH")
        yield external.rstrip("/"), Path(external_db) if external_db else None
        return

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    temp_dir = Path(tempfile.mkdtemp(prefix="shoplite-"))
    db_path = temp_dir / "shoplite.db"
    log_path = temp_dir / "uvicorn.log"
    log_file = log_path.open("w", encoding="utf-8")

    env = os.environ.copy()
    env["SHOPLITE_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        deadline = time.time() + 45
        while time.time() < deadline:
            if proc.poll() is not None:
                log_file.flush()
                detail = log_path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(f"ShopLite 启动失败：\n{detail[-4000:]}")
            try:
                if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.2)
        else:
            log_file.flush()
            detail = log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"ShopLite 45 秒内没有启动：\n{detail[-4000:]}")

        yield base_url, db_path
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log_file.close()


@pytest.fixture(scope="session")
def base_url(demo_server) -> str:
    return demo_server[0]


@pytest.fixture(scope="session")
def db_path(demo_server) -> Path:
    path = demo_server[1]
    if path is None:
        pytest.skip("当前是外部服务模式，没有可断言的测试数据库")
    return path


@pytest.fixture()
def api(base_url: str):
    client = ApiClient(base_url)
    yield client
    client.close()


@pytest.fixture()
def user_factory(api: ApiClient):
    def create(username: str | None = None, password: str = "Passw0rd!") -> dict:
        username = username or f"qa_{uuid.uuid4().hex[:10]}"
        response = api.post(
            "/api/auth/register",
            json={"username": username, "password": password},
        )
        assert response.status_code == 201, response.text
        return {
            "id": response.json()["id"],
            "username": username,
            "password": password,
        }

    return create


@pytest.fixture()
def user(user_factory) -> dict:
    return user_factory()


@pytest.fixture()
def auth_api(api: ApiClient, user: dict) -> ApiClient:
    response = api.login(user["username"], user["password"])
    assert response.status_code == 200, response.text
    return api


@pytest.fixture()
def products(api: ApiClient) -> list[dict]:
    response = api.get("/api/products")
    assert response.status_code == 200, response.text
    return response.json()["items"]


@pytest.fixture()
def find_product(products: list[dict]):
    def find(name: str) -> dict:
        for product in products:
            if product["name"] == name:
                return product
        raise AssertionError(f"商品不存在：{name}；可选：{[p['name'] for p in products]}")

    return find


@pytest.fixture()
def login_as(page, user: dict):
    """UI 用例的快捷登录：先通过 API 建用户，再走真实登录页面。"""

    def do_login():
        from pages.login_page import LoginPage

        login_page = LoginPage(page)
        login_page.goto()
        return login_page.login(user["username"], user["password"])

    return do_login


# ---------------------------------------------------------------------------
# Playwright：整个会话只启动一次浏览器，每个用例一个干净的 Context
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser():
    settings = get_settings()
    with sync_playwright() as playwright:
        launch_kwargs = {
            "headless": settings.headless,
            "slow_mo": settings.slow_mo,
        }
        if settings.browser and settings.browser != "chromium":
            launch_kwargs["channel"] = settings.browser

        try:
            browser = playwright.chromium.launch(**launch_kwargs)
        except PlaywrightError:
            if "channel" not in launch_kwargs:
                raise
            launch_kwargs.pop("channel")
            browser = playwright.chromium.launch(**launch_kwargs)

        yield browser
        browser.close()


@pytest.fixture()
def page(browser, base_url: str, request):
    settings = get_settings()
    context = browser.new_context(
        base_url=base_url,
        viewport={"width": 1440, "height": 960},
        locale="zh-CN",
    )
    page = context.new_page()
    page.set_default_timeout(settings.timeout_ms)

    yield page

    failed = any(
        getattr(request.node, f"rep_{when}", None)
        and getattr(request.node, f"rep_{when}").failed
        for when in ("setup", "call", "teardown")
    )
    if failed:
        try:
            screenshot = page.screenshot(full_page=True)
            allure.attach(
                screenshot,
                name="失败截图",
                attachment_type=allure.attachment_type.PNG,
            )
            allure.attach(
                page.content(),
                name="失败页面 HTML",
                attachment_type=allure.attachment_type.HTML,
            )
        except Exception:
            pass

    context.close()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def pytest_sessionfinish(session, exitstatus):
    """把环境信息写进 Allure，报告首页不再显示空白。"""
    results_dir = PROJECT_ROOT / "reports" / "allure-results"
    results_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    environment = {
        "Python": platform.python_version(),
        "Platform": platform.platform(),
        "Browser": settings.browser,
        "Headless": str(settings.headless).lower(),
        "BaseURL": settings.base_url or "auto-started ShopLite",
        "TestFramework": "pytest + requests + Playwright",
    }
    (results_dir / "environment.properties").write_text(
        "\n".join(f"{key}={value}" for key, value in environment.items()),
        encoding="utf-8",
    )
    (results_dir / "executor.json").write_text(
        json.dumps(
            {
                "name": "ShopQA Local",
                "type": "local",
                "buildName": f"local-{time.strftime('%Y%m%d-%H%M%S')}",
                "reportName": "ShopQA E-commerce Test Report",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
