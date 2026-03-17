# Inventory Refresh Gateway Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变购买运行时、库存状态机和对外接口的前提下，把库存刷新链路从 legacy `autobuy.py` 中剥离出来，接入新架构自己的库存刷新网关。

**Architecture:** 新增一个新的库存刷新网关，内部完成 preview 请求构造、签名、发送和响应解析，并继续返回 `InventoryRefreshResult`。`PurchaseRuntimeService`、`InventoryState`、恢复检查和快照持久化逻辑保持现有行为不变，只替换默认库存刷新网关来源。

**Tech Stack:** Python, asyncio, aiohttp, pytest, Node.js-backed `xsign.py`

---

## 文件结构

- Create: `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
  - 新的库存刷新网关，负责 preview 请求和仓库列表解析
- Modify: `app_backend/main.py`
  - 默认库存刷新网关从旧实现切到新网关
- Modify: `app_backend/infrastructure/purchase/runtime/__init__.py`
  - 导出新库存刷新网关
- Create: `tests/backend/test_inventory_refresh_gateway.py`
  - 覆盖新网关主路径、鉴权、异常和请求形状
- Modify: `tests/backend/test_inventory_runtime_gateway_wiring.py`
  - 改为验证新网关兼容旧 preview 请求语义，并锁定默认接线
- Verify: `tests/backend/test_purchase_runtime_service.py`
  - 确认启动刷新、购买后远程刷新和恢复检查行为不回归
- Verify: `tests/backend/test_purchase_runtime_routes.py`
  - 确认 app 默认接线和运行时接口不回归
- Modify: `README.md`
  - 更新库存刷新去 legacy 进度

## Chunk 1: 库存刷新网关单测先行

### Task 1: 写 `InventoryRefreshGateway` 的失败测试

**Files:**
- Create: `tests/backend/test_inventory_refresh_gateway.py`
- Create: `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`

- [ ] **Step 1: 写失败测试，锁定“成功拿到 receiveSteamList”主路径**

```python
async def test_inventory_refresh_gateway_fetches_preview_inventories():
    signer = FakeSigner(result="fake-sign")
    session = FakeSession(
        responses=[
            (
                200,
                json.dumps(
                    {
                        "success": True,
                        "data": {
                            "receiveSteamList": [
                                {"nickname": "alpha", "steamId": "steam-1", "inventoryNum": 920, "inventoryMaxNum": 1000},
                                {"nickname": "beta", "steamId": "steam-2", "inventoryNum": 880, "inventoryMaxNum": 1000},
                            ]
                        },
                    }
                ),
            )
        ]
    )
    gateway = InventoryRefreshGateway(xsign_wrapper=signer)
    result = await gateway.refresh(account=build_account())
    assert result.status == "success"
    assert [item["steamId"] for item in result.inventories] == ["steam-1", "steam-2"]
```

- [ ] **Step 2: 写失败测试，锁定 `Not login / 403` 映射为 `auth_invalid`**

```python
async def test_inventory_refresh_gateway_returns_auth_invalid_when_cookie_missing_auth_fields():
    ...
    assert result.status == "auth_invalid"


async def test_inventory_refresh_gateway_maps_not_login_to_auth_invalid():
    ...
    assert result.status == "auth_invalid"


async def test_inventory_refresh_gateway_maps_403_to_auth_invalid():
    ...
    assert result.status == "auth_invalid"
```

- [ ] **Step 3: 写失败测试，锁定异常与错误文本**

```python
async def test_inventory_refresh_gateway_returns_xsign_error_text():
    ...
    assert result.status == "error"
    assert result.error == "x-sign生成失败: boom"


async def test_inventory_refresh_gateway_returns_timeout_text():
    ...
    assert result.error == "请求超时"


async def test_inventory_refresh_gateway_returns_request_failed_text():
    ...
    assert result.error == "请求失败: network down"


async def test_inventory_refresh_gateway_returns_invalid_json_text():
    ...
    assert result.error == "响应不是有效的JSON格式"
```

- [ ] **Step 4: 写失败测试，锁定 preview 请求体和请求头形状**

```python
async def test_inventory_refresh_gateway_keeps_legacy_preview_request_shape():
    ...
    assert session.calls[0]["url"].endswith("/support/trade/product/batch/v1/preview/1380979899390267393")
    assert session.calls[0]["json"] == {"itemId": "1380979899390267393"}
    assert session.calls[0]["headers"]["Cookie"] == build_account().cookie_raw
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
```

- [ ] **Step 5: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_refresh_gateway.py -q`
Expected: FAIL，提示 `InventoryRefreshGateway` 不存在或行为未实现

## Chunk 2: 最小实现库存刷新网关

### Task 2: 实现 `InventoryRefreshGateway`

**Files:**
- Create: `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
- Create: `tests/backend/test_inventory_refresh_gateway.py`

- [ ] **Step 1: 实现固定 preview 请求常量和请求体**

```python
class InventoryRefreshGateway:
    _PREVIEW_ITEM_ID = "1380979899390267393"
    _PREVIEW_PRODUCT_URL = "https://www.c5game.com/..."
    _API_PATH = f"support/trade/product/batch/v1/preview/{_PREVIEW_ITEM_ID}"

    @classmethod
    def build_request_body(cls) -> dict[str, str]:
        return {"itemId": cls._PREVIEW_ITEM_ID}
```

- [ ] **Step 2: 实现请求头构建，保持 legacy 语义**

```python
def _build_headers(self, *, runtime_account, timestamp: str, x_sign: str) -> OrderedDict[str, str] | None:
    ...
    headers["Referer"] = self._PREVIEW_PRODUCT_URL
    headers["Cookie"] = runtime_account.get_cookie_header_exact()
    headers["x-device-id"] = device_id
    headers["x-start-req-time"] = timestamp
    headers["x-sign"] = x_sign
    headers["x-access-token"] = access_token
```

- [ ] **Step 3: 实现响应解析和错误映射**

```python
@classmethod
def parse_response(cls, text: str) -> InventoryRefreshResult:
    ...
    if "not login" in normalized or "403" in normalized:
        return InventoryRefreshResult.auth_invalid(error_msg)
    return InventoryRefreshResult(status="error", inventories=[], error=f"请求失败: {error_msg}")
```

- [ ] **Step 4: 实现 `refresh()`，直接使用 `xsign.py + test.wasm`**

```python
async def refresh(self, *, account) -> InventoryRefreshResult:
    runtime_account = account if isinstance(account, RuntimeAccountAdapter) else RuntimeAccountAdapter(account)
    ...
    session = await runtime_account.get_global_session()
    ...
```

- [ ] **Step 5: 复跑库存刷新网关测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_refresh_gateway.py -q`
Expected: PASS

## Chunk 3: 切换默认库存刷新接线

### Task 3: 让 app 默认使用新库存刷新网关

**Files:**
- Modify: `app_backend/main.py`
- Modify: `app_backend/infrastructure/purchase/runtime/__init__.py`
- Modify: `tests/backend/test_inventory_runtime_gateway_wiring.py`

- [ ] **Step 1: 改写兼容烟测，锁定新网关仍保持旧 preview 请求语义**

```python
async def test_inventory_refresh_gateway_smoke_keeps_legacy_preview_request_shape():
    ...
    assert session.calls[0]["json"] == {"itemId": "1380979899390267393"}
    assert session.calls[0]["headers"]["x-sign"] == "fake-sign"
```

- [ ] **Step 2: 新增默认接线测试，锁定 `create_app()` 使用新网关**

```python
def test_create_app_uses_inventory_refresh_gateway_by_default(tmp_path):
    app = create_app(db_path=tmp_path / "app.db")
    assert app.state.purchase_runtime_service._inventory_refresh_gateway_factory is InventoryRefreshGateway
```

- [ ] **Step 3: 运行兼容烟测确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_runtime_gateway_wiring.py -q`
Expected: FAIL，提示仍绑定 legacy 网关或新网关未接入

- [ ] **Step 4: 修改默认接线和运行时导出**

```python
from app_backend.infrastructure.purchase.runtime.inventory_refresh_gateway import InventoryRefreshGateway
...
inventory_refresh_gateway_factory=InventoryRefreshGateway
```

- [ ] **Step 5: 复跑兼容烟测**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_runtime_gateway_wiring.py -q`
Expected: PASS

## Chunk 4: 购买运行时回归

### Task 4: 确认运行时行为不回归

**Files:**
- Verify: `tests/backend/test_purchase_runtime_service.py`
- Verify: `tests/backend/test_purchase_runtime_routes.py`

- [ ] **Step 1: 运行购买运行时回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py -q`
Expected: PASS

- [ ] **Step 2: 运行购买运行时路由回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 3: 只有测试失败时才做最小修正**

```python
if refresh_result.status == "success":
    ...
elif refresh_result.status == "auth_invalid":
    ...
```

- [ ] **Step 4: 复跑运行时回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

## Chunk 5: 最终验证

### Task 5: 整体验证库存刷新替换不破外部合同

**Files:**
- Modify: `README.md`
- Verify only

- [ ] **Step 1: 更新 README 中购买链路去 legacy 进度**

```markdown
- 库存刷新链路已从 `autobuy.py` 中剥离
- 购买模块运行时已不再依赖 legacy `autobuy.py`
```

- [ ] **Step 2: 运行库存刷新替换相关定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory_refresh_gateway.py tests/backend/test_inventory_runtime_gateway_wiring.py tests/backend/test_purchase_runtime_service.py tests/backend/test_purchase_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 3: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 4: 汇报结果，只报告已验证内容**

注：

- 本计划不包含 git 提交
- 相关 legacy gateway 已在后续清理完成
