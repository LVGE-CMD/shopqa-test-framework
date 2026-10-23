"""接口契约（JSON Schema）。

这些 schema 是“接口文档的可执行版本”。接口如果偷偷把 price_cents
从整数改成字符串，或者少返回一个字段，测试会直接失败。
"""

USER_SCHEMA = {
    "type": "object",
    "required": ["id", "username"],
    "properties": {
        "id": {"type": "integer"},
        "username": {"type": "string"},
        "created_at": {"type": "string"},
    },
}

LOGIN_SCHEMA = {
    "type": "object",
    "required": ["access_token", "token_type", "user"],
    "properties": {
        "access_token": {"type": "string", "minLength": 20},
        "token_type": {"type": "string", "enum": ["bearer"]},
        "user": USER_SCHEMA,
    },
}

PRODUCT_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "description", "price_cents", "stock", "emoji"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "price_cents": {"type": "integer", "minimum": 0},
        "stock": {"type": "integer", "minimum": 0},
        "emoji": {"type": "string"},
    },
}

PRODUCT_LIST_SCHEMA = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": PRODUCT_SCHEMA},
        "total": {"type": "integer", "minimum": 0},
    },
}

CART_ITEM_SCHEMA = {
    "type": "object",
    "required": [
        "product_id",
        "name",
        "price_cents",
        "quantity",
        "line_total_cents",
        "stock",
    ],
    "properties": {
        "product_id": {"type": "integer"},
        "name": {"type": "string"},
        "price_cents": {"type": "integer", "minimum": 0},
        "quantity": {"type": "integer", "minimum": 1},
        "line_total_cents": {"type": "integer", "minimum": 0},
        "stock": {"type": "integer", "minimum": 0},
    },
}

CART_SCHEMA = {
    "type": "object",
    "required": ["items", "subtotal_cents", "total_quantity"],
    "properties": {
        "items": {"type": "array", "items": CART_ITEM_SCHEMA},
        "subtotal_cents": {"type": "integer", "minimum": 0},
        "total_quantity": {"type": "integer", "minimum": 0},
    },
}

ORDER_SCHEMA = {
    "type": "object",
    "required": [
        "id",
        "order_no",
        "subtotal_cents",
        "discount_cents",
        "total_cents",
        "status",
        "items",
    ],
    "properties": {
        "id": {"type": "integer"},
        "order_no": {"type": "string", "pattern": r"^ORD-\d{14}-[0-9A-F]{4}$"},
        "subtotal_cents": {"type": "integer", "minimum": 0},
        "discount_cents": {"type": "integer", "minimum": 0},
        "total_cents": {"type": "integer", "minimum": 0},
        "coupon_code": {"type": ["string", "null"]},
        "status": {"type": "string"},
        "items": {"type": "array", "minItems": 1},
    },
}

ORDER_SUMMARY_SCHEMA = {
    "type": "object",
    "required": [
        "id",
        "order_no",
        "subtotal_cents",
        "discount_cents",
        "total_cents",
        "status",
        "item_count",
    ],
    "properties": {
        "id": {"type": "integer"},
        "order_no": {"type": "string"},
        "subtotal_cents": {"type": "integer", "minimum": 0},
        "discount_cents": {"type": "integer", "minimum": 0},
        "total_cents": {"type": "integer", "minimum": 0},
        "status": {"type": "string"},
        "item_count": {"type": "integer", "minimum": 1},
    },
}

ORDER_LIST_SCHEMA = {
    "type": "object",
    "required": ["items", "total"],
    "properties": {
        "items": {"type": "array", "items": ORDER_SUMMARY_SCHEMA},
        "total": {"type": "integer", "minimum": 0},
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "required": ["detail"],
    "properties": {"detail": {"type": "string"}},
}
