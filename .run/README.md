# 运行配置说明

PyCharm 打开项目后，右上角可以选择以下配置：

| 配置 | 作用 |
|---|---|
| `ShopQA All Tests` | 全量 54 条 |
| `ShopQA Smoke` | 冒烟 6 条 |
| `ShopQA API Tests` | 只跑接口 41 条 |
| `ShopQA UI Tests (watch)` | 有头浏览器，slow_mo=200ms，方便看操作 |
| `ShopLite App (8000)` | 启动被测系统，浏览器手工体验 |

解释器：

```text
D:\Projects\shopqa-test-framework\.venv\Scripts\python.exe
```

如果运行配置没有自动出现：`File → Reload from Disk`，或检查 `Settings → Project → Python Interpreter` 是否指向 `.venv`。
