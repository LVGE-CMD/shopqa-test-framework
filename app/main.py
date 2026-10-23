"""ShopLite：一个专门给自动化测试练习用的迷你电商系统。

同一个服务同时提供：
1. Web 页面：登录、商品、购物车、结算、订单；
2. JSON API：给 requests / pytest 做接口自动化；
3. SQLite：给测试做数据库断言。

真实项目里被测系统通常由开发团队维护；这里把它内置，是为了让整套
测试框架不依赖外网、不依赖别人的 Demo 站点，面试时随时可以运行。
"""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field

from app.db import (
    DEMO_PASSWORD,
    DEMO_USERNAME,
    db,
    hash_password,
    init_db,
    seed,
    token_digest,
    verify_password,
)

BASE_DIR = Path(__file__).resolve().parent
SESSION_COOKIE = "shoplite_session"
COUPON_CODE = "QA10"
COUPON_MIN_SUBTOTAL = 10_000  # 100.00 元


class BusinessError(Exception):
    """业务规则错误：由路由统一转换成 4xx，而不是 500。"""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[A-Za-z0-9_]+$",
        examples=["qa_user"],
    )
    password: str = Field(min_length=8, max_length=64, examples=["Passw0rd!"])


class LoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str
    password: str


class CartItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class OrderIn(BaseModel):
    coupon_code: str | None = Field(default=None, max_length=20)


def user_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "created_at": row["created_at"],
    }


def product_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "price_cents": row["price_cents"],
        "stock": row["stock"],
        "emoji": row["emoji"],
    }


def resolve_user(request: Request) -> dict | None:
    """同时支持两种登录态：
    - API：Authorization: Bearer <token>
    - 浏览器：HttpOnly Cookie
    """
    token: str | None = None
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    with db() as conn:
        row = conn.execute(
            """
            SELECT u.*
            FROM tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = ?
            """,
            (token_digest(token),),
        ).fetchone()
    return user_public(row) if row else None


def current_user(request: Request) -> dict:
    user = resolve_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或 token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute(
            "INSERT INTO tokens (token_hash, user_id) VALUES (?, ?)",
            (token_digest(token), user_id),
        )
    return token


def revoke_token(token: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM tokens WHERE token_hash = ?", (token_digest(token),))


def cart_payload(user_id: int) -> dict:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT ci.product_id, ci.quantity, p.name, p.description,
                   p.price_cents, p.stock, p.emoji
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.user_id = ?
            ORDER BY ci.added_at, ci.product_id
            """,
            (user_id,),
        ).fetchall()

    items = []
    subtotal = 0
    for row in rows:
        line_total = row["price_cents"] * row["quantity"]
        subtotal += line_total
        items.append(
            {
                "product_id": row["product_id"],
                "name": row["name"],
                "description": row["description"],
                "price_cents": row["price_cents"],
                "quantity": row["quantity"],
                "stock": row["stock"],
                "emoji": row["emoji"],
                "line_total_cents": line_total,
            }
        )
    return {
        "items": items,
        "subtotal_cents": subtotal,
        "total_quantity": sum(item["quantity"] for item in items),
    }


def cart_quantity(user_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM cart_items WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["quantity"])


def add_to_cart(user_id: int, product_id: int, quantity: int) -> None:
    if not 1 <= quantity <= 99:
        raise BusinessError(422, "购买数量必须在 1 到 99 之间")

    with db() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE id = ? AND active = 1", (product_id,)
        ).fetchone()
        if product is None:
            raise BusinessError(404, "商品不存在或已下架")

        existing = conn.execute(
            "SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        ).fetchone()
        new_quantity = quantity + (existing["quantity"] if existing else 0)
        if new_quantity > product["stock"]:
            raise BusinessError(
                400,
                f"{product['name']} 库存不足，最多还能购买 "
                f"{max(product['stock'] - (existing['quantity'] if existing else 0), 0)} 件",
            )

        conn.execute(
            """
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id)
            DO UPDATE SET quantity = excluded.quantity
            """,
            (user_id, product_id, new_quantity),
        )


def update_cart_quantity(user_id: int, product_id: int, quantity: int) -> None:
    if not 1 <= quantity <= 99:
        raise BusinessError(422, "购买数量必须在 1 到 99 之间")

    with db() as conn:
        item = conn.execute(
            "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        ).fetchone()
        if item is None:
            raise BusinessError(404, "购物车里没有这件商品")

        product = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if product is None:
            raise BusinessError(404, "商品不存在")
        if quantity > product["stock"]:
            raise BusinessError(400, f"库存不足，当前最多可购买 {product['stock']} 件")

        conn.execute(
            "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
            (quantity, user_id, product_id),
        )


def remove_cart_item(user_id: int, product_id: int) -> None:
    with db() as conn:
        cursor = conn.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
    if cursor.rowcount == 0:
        raise BusinessError(404, "购物车里没有这件商品")


def place_order(user_id: int, coupon_code: str | None = None) -> int:
    cart = cart_payload(user_id)
    if not cart["items"]:
        raise BusinessError(400, "购物车为空，不能结算")

    subtotal = cart["subtotal_cents"]
    code = (coupon_code or "").strip().upper()
    discount = 0
    if code:
        if code != COUPON_CODE:
            raise BusinessError(400, "优惠券不存在")
        if subtotal < COUPON_MIN_SUBTOTAL:
            raise BusinessError(400, "优惠券 QA10 需满 ¥100.00 可用")
        discount = subtotal * 10 // 100

    total = subtotal - discount
    order_no = f"ORD-{datetime.now():%Y%m%d%H%M%S}-{secrets.token_hex(2).upper()}"

    with db() as conn:
        # 下单前再查一次库存，避免购物车加入后库存被其他订单买走。
        for item in cart["items"]:
            product = conn.execute(
                "SELECT stock FROM products WHERE id = ?", (item["product_id"],)
            ).fetchone()
            if product is None or product["stock"] < item["quantity"]:
                raise BusinessError(400, f"{item['name']} 库存不足，请调整数量")

        cursor = conn.execute(
            """
            INSERT INTO orders (
                order_no, user_id, subtotal_cents, discount_cents,
                total_cents, coupon_code, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'paid')
            """,
            (order_no, user_id, subtotal, discount, total, code or None),
        )
        order_id = int(cursor.lastrowid)

        for item in cart["items"]:
            conn.execute(
                """
                INSERT INTO order_items (
                    order_id, product_id, product_name, unit_price_cents,
                    quantity, line_total_cents
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    item["price_cents"],
                    item["quantity"],
                    item["line_total_cents"],
                ),
            )
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item["quantity"], item["product_id"]),
            )

        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))

    return order_id


def order_payload(order_id: int, user_id: int) -> dict:
    with db() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)
        ).fetchone()
        if order is None:
            raise BusinessError(404, "订单不存在")
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)
        ).fetchall()

    return {
        "id": order["id"],
        "order_no": order["order_no"],
        "subtotal_cents": order["subtotal_cents"],
        "discount_cents": order["discount_cents"],
        "total_cents": order["total_cents"],
        "coupon_code": order["coupon_code"],
        "status": order["status"],
        "created_at": order["created_at"],
        "items": [
            {
                "product_id": item["product_id"],
                "name": item["product_name"],
                "unit_price_cents": item["unit_price_cents"],
                "quantity": item["quantity"],
                "line_total_cents": item["line_total_cents"],
            }
            for item in items
        ],
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed()
    yield


app = FastAPI(title="ShopLite Demo API", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def money(cents: int) -> str:
    return f"¥{cents / 100:.2f}"


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["money"] = money


def page_context(request: Request, **extra) -> dict:
    user = resolve_user(request)
    context = {
        "request": request,
        "current_user": user,
        "cart_count": cart_quantity(user["id"]) if user else 0,
        "error": request.query_params.get("error"),
        "message": request.query_params.get("message"),
    }
    context.update(extra)
    return context


def render(request: Request, name: str, status_code: int = 200, **extra):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=page_context(request, **extra),
        status_code=status_code,
    )


def redirect(path: str, *, error: str | None = None, message: str | None = None):
    params = {}
    if error:
        params["error"] = error
    if message:
        params["message"] = message
    url = f"{path}?{urlencode(params)}" if params else path
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def login_required(request: Request, redirect_to: str = "/products"):
    user = resolve_user(request)
    if user is None:
        return None, redirect("/login", error=f"请先登录后再访问 {redirect_to}")
    return user, None


# ---------------------------------------------------------------------------
# Web UI：给 Playwright 做页面自动化
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return redirect("/products" if resolve_user(request) else "/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if resolve_user(request):
        return redirect("/products")
    return render(request, "login.html", demo_username=DEMO_USERNAME, demo_password=DEMO_PASSWORD)


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()

    if row is None or not verify_password(password, row["password_hash"]):
        return render(
            request,
            "login.html",
            status_code=401,
            error="用户名或密码错误",
            demo_username=DEMO_USERNAME,
            demo_password=DEMO_PASSWORD,
            username=username,
        )

    token = issue_token(row["id"])
    response = redirect("/products", message=f"欢迎回来，{row['username']}")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=86_400,
    )
    return response


@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_token(token)
    response = redirect("/login", message="已退出登录")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request, q: str = Query(default="")):
    user, redirect_response = login_required(request, "/products")
    if redirect_response:
        return redirect_response

    keyword = q.strip()
    with db() as conn:
        if keyword:
            rows = conn.execute(
                """
                SELECT * FROM products
                WHERE active = 1 AND LOWER(name) LIKE LOWER(?)
                ORDER BY id
                """,
                (f"%{keyword}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products WHERE active = 1 ORDER BY id"
            ).fetchall()

    return render(
        request,
        "products.html",
        products=[product_public(row) for row in rows],
        keyword=keyword,
    )


@app.post("/cart/add")
def cart_add(
    request: Request,
    product_id: Annotated[int, Form()],
    quantity: Annotated[int, Form()] = 1,
):
    user, redirect_response = login_required(request, "/cart")
    if redirect_response:
        return redirect_response
    try:
        add_to_cart(user["id"], product_id, quantity)
    except BusinessError as exc:
        return redirect("/products", error=exc.detail)
    return redirect("/cart", message="已加入购物车")


@app.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request):
    user, redirect_response = login_required(request, "/cart")
    if redirect_response:
        return redirect_response
    return render(request, "cart.html", cart=cart_payload(user["id"]))


@app.post("/cart/update")
def cart_update(
    request: Request,
    product_id: Annotated[int, Form()],
    quantity: Annotated[int, Form()],
):
    user, redirect_response = login_required(request, "/cart")
    if redirect_response:
        return redirect_response
    try:
        update_cart_quantity(user["id"], product_id, quantity)
    except BusinessError as exc:
        return redirect("/cart", error=exc.detail)
    return redirect("/cart", message="数量已更新")


@app.post("/cart/remove")
def cart_remove(request: Request, product_id: Annotated[int, Form()]):
    user, redirect_response = login_required(request, "/cart")
    if redirect_response:
        return redirect_response
    try:
        remove_cart_item(user["id"], product_id)
    except BusinessError as exc:
        return redirect("/cart", error=exc.detail)
    return redirect("/cart", message="已从购物车移除")


@app.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request):
    user, redirect_response = login_required(request, "/checkout")
    if redirect_response:
        return redirect_response
    cart = cart_payload(user["id"])
    if not cart["items"]:
        return redirect("/cart", error="购物车为空，先去挑件商品吧")
    return render(request, "checkout.html", cart=cart, coupon_code="")


@app.post("/checkout", response_class=HTMLResponse)
def checkout_submit(request: Request, coupon_code: Annotated[str, Form()] = ""):
    user, redirect_response = login_required(request, "/checkout")
    if redirect_response:
        return redirect_response
    try:
        order_id = place_order(user["id"], coupon_code)
    except BusinessError as exc:
        cart = cart_payload(user["id"])
        return render(
            request,
            "checkout.html",
            status_code=exc.status_code,
            cart=cart,
            coupon_code=coupon_code,
            error=exc.detail,
        )
    return redirect(f"/orders/{order_id}", message="下单成功")


@app.get("/orders", response_class=HTMLResponse)
def orders_page(request: Request):
    user, redirect_response = login_required(request, "/orders")
    if redirect_response:
        return redirect_response
    with db() as conn:
        rows = conn.execute(
            """
            SELECT o.*,
                   (SELECT COALESCE(SUM(quantity), 0)
                    FROM order_items oi WHERE oi.order_id = o.id) AS item_count
            FROM orders o
            WHERE o.user_id = ?
            ORDER BY o.id DESC
            """,
            (user["id"],),
        ).fetchall()
    orders = [
        {
            "id": row["id"],
            "order_no": row["order_no"],
            "total_cents": row["total_cents"],
            "discount_cents": row["discount_cents"],
            "status": row["status"],
            "created_at": row["created_at"],
            "item_count": row["item_count"],
        }
        for row in rows
    ]
    return render(request, "orders.html", orders=orders)


@app.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail_page(request: Request, order_id: int):
    user, redirect_response = login_required(request, f"/orders/{order_id}")
    if redirect_response:
        return redirect_response
    try:
        order = order_payload(order_id, user["id"])
    except BusinessError:
        return redirect("/orders", error="订单不存在")
    return render(request, "order_detail.html", order=order)


# ---------------------------------------------------------------------------
# JSON API：给 pytest + requests 做接口自动化
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "shoplite"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def api_register(payload: RegisterIn):
    with db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (payload.username, hash_password(payload.password)),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="用户名已存在")
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return user_public(row)


@app.post("/api/auth/login")
def api_login(payload: LoginIn):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (payload.username,)
        ).fetchone()
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "access_token": issue_token(row["id"]),
        "token_type": "bearer",
        "user": user_public(row),
    }


@app.get("/api/auth/me")
def api_me(user: dict = Depends(current_user)):
    return user


@app.get("/api/products")
def api_products(q: str = Query(default="")):
    keyword = q.strip()
    with db() as conn:
        if keyword:
            rows = conn.execute(
                """
                SELECT * FROM products
                WHERE active = 1 AND LOWER(name) LIKE LOWER(?)
                ORDER BY id
                """,
                (f"%{keyword}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM products WHERE active = 1 ORDER BY id"
            ).fetchall()
    items = [product_public(row) for row in rows]
    return {"items": items, "total": len(items)}


@app.get("/api/products/{product_id}")
def api_product_detail(product_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE id = ? AND active = 1", (product_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product_public(row)


@app.get("/api/cart")
def api_cart(user: dict = Depends(current_user)):
    return cart_payload(user["id"])


@app.post("/api/cart/items")
def api_cart_add(payload: CartItemIn, user: dict = Depends(current_user)):
    try:
        add_to_cart(user["id"], payload.product_id, payload.quantity)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return cart_payload(user["id"])


@app.patch("/api/cart/items/{product_id}")
def api_cart_update(
    product_id: int, payload: CartItemUpdate, user: dict = Depends(current_user)
):
    try:
        update_cart_quantity(user["id"], product_id, payload.quantity)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return cart_payload(user["id"])


@app.delete("/api/cart/items/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def api_cart_delete(product_id: int, user: dict = Depends(current_user)):
    try:
        remove_cart_item(user["id"], product_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def api_create_order(payload: OrderIn | None = None, user: dict = Depends(current_user)):
    try:
        order_id = place_order(user["id"], payload.coupon_code if payload else None)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return order_payload(order_id, user["id"])


@app.get("/api/orders")
def api_orders(user: dict = Depends(current_user)):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT o.*,
                   (SELECT COALESCE(SUM(quantity), 0)
                    FROM order_items oi WHERE oi.order_id = o.id) AS item_count
            FROM orders o
            WHERE o.user_id = ?
            ORDER BY o.id DESC
            """,
            (user["id"],),
        ).fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "order_no": row["order_no"],
                "subtotal_cents": row["subtotal_cents"],
                "discount_cents": row["discount_cents"],
                "total_cents": row["total_cents"],
                "coupon_code": row["coupon_code"],
                "status": row["status"],
                "created_at": row["created_at"],
                "item_count": row["item_count"],
            }
            for row in rows
        ],
        "total": len(rows),
    }


@app.get("/api/orders/{order_id}")
def api_order_detail(order_id: int, user: dict = Depends(current_user)):
    try:
        return order_payload(order_id, user["id"])
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
