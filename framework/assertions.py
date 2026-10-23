from __future__ import annotations

import json
from typing import Any

import jsonschema


def assert_status(response, expected: int) -> None:
    """失败时把响应体带出来，排查比只看到一条 assert 快得多。"""
    assert response.status_code == expected, (
        f"期望状态码 {expected}，实际 {response.status_code}\n"
        f"响应体：{response.text[:2000]}"
    )


def assert_json_contains(actual: Any, expected: Any, path: str = "$") -> None:
    """递归子集断言：只校验关心的字段，不排斥接口新增字段。"""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path} 期望对象，实际是 {type(actual).__name__}"
        for key, value in expected.items():
            assert key in actual, f"{path} 缺少字段 {key!r}，实际字段：{list(actual)}"
            assert_json_contains(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path} 期望数组，实际是 {type(actual).__name__}"
        assert len(actual) == len(expected), (
            f"{path} 长度不一致：期望 {len(expected)}，实际 {len(actual)}"
        )
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            assert_json_contains(actual_item, expected_item, f"{path}[{index}]")
    else:
        assert actual == expected, f"{path} 期望 {expected!r}，实际 {actual!r}"


def assert_schema(instance: Any, schema: dict, label: str = "response") -> None:
    """JSON Schema 校验，保证字段类型和必填项没有悄悄变化。"""
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as exc:
        raise AssertionError(
            f"{label} 不符合 JSON Schema：{exc.message}\n"
            f"路径：{list(exc.absolute_path)}\n"
            f"数据：{json.dumps(instance, ensure_ascii=False)[:1500]}"
        ) from exc
