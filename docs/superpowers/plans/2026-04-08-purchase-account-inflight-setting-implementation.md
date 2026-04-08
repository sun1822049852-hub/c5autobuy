# Purchase Account Inflight Setting Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将“单账号最大并发购买任务数”加入现有购买设置，默认值改为 1，并在存在在途购买时延迟到当前购买完成后再生效。

**Architecture:** 继续复用现有 `/runtime-settings/purchase` 持久化链路，把 `max_inflight_per_account` 与 `per_batch_ip_fanout_limit` 并列存入 `purchase_settings_json`。购买 runtime 不在购买中途切换并发上限，而是在保存后记录 pending settings，并在最后一个在途 dispatch 完成时统一同步到 scheduler 与 dispatch runner。

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, React, Vitest

---

## Chunk 1: 后端设置链路

### Task 1: 扩展 runtime settings 模型、接口与默认值

**Files:**
- Modify: `app_backend/api/schemas/runtime_settings.py`
- Modify: `app_backend/api/routes/runtime_settings.py`
- Modify: `app_backend/application/use_cases/update_purchase_runtime_settings.py`
- Modify: `app_backend/application/use_cases/get_app_bootstrap.py`
- Modify: `app_backend/infrastructure/repositories/runtime_settings_repository.py`
- Test: `tests/backend/test_runtime_settings_repository.py`
- Test: `tests/backend/test_runtime_settings_routes.py`
- Test: `tests/backend/test_app_bootstrap_route.py`
- Test: `tests/backend/test_runtime_update_websocket.py`

- [ ] **Step 1: 写失败测试，锁定新字段默认值和接口读写**

在 `tests/backend/test_runtime_settings_repository.py`、`tests/backend/test_runtime_settings_routes.py`、`tests/backend/test_app_bootstrap_route.py`、`tests/backend/test_runtime_update_websocket.py` 增加断言：

```python
assert settings.purchase_settings_json == {
    "per_batch_ip_fanout_limit": 1,
    "max_inflight_per_account": 1,
}
```

```python
assert response.json() == {
    "per_batch_ip_fanout_limit": 1,
    "max_inflight_per_account": 1,
    "updated_at": None,
}
```

```python
json={
    "per_batch_ip_fanout_limit": 4,
    "max_inflight_per_account": 2,
}
```

- [ ] **Step 2: 跑后端设置相关测试，确认红灯**

Run:

```bash
pytest tests/backend/test_runtime_settings_repository.py tests/backend/test_runtime_settings_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q
```

Expected:

- 至少有新字段缺失相关失败

- [ ] **Step 3: 写最小实现**

实现要点：

- `PurchaseRuntimeSettingsResponse` / `PurchaseRuntimeSettingsUpdateRequest` 增加 `max_inflight_per_account`
- `UpdatePurchaseRuntimeSettingsUseCase.execute(...)` 同时校验并保存两个字段
- repository 默认值补齐新字段
- `/runtime-settings/purchase` 的序列化与更新逻辑补齐新字段
- `app/bootstrap` 里的 `purchase_system.runtime_settings` 返回新字段

- [ ] **Step 4: 再跑后端设置相关测试，确认绿灯**

Run:

```bash
pytest tests/backend/test_runtime_settings_repository.py tests/backend/test_runtime_settings_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q
```

Expected:

- PASS

## Chunk 2: 购买 runtime 延迟生效

### Task 2: 让 `max_inflight_per_account` 从 settings 读取，并在在途购买结束后生效

**Files:**
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_scheduler.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`
- Modify: `app_backend/main.py`
- Test: `tests/backend/test_purchase_runtime_service.py`

- [ ] **Step 1: 写失败测试，锁定默认读取与延迟生效**

在 `tests/backend/test_purchase_runtime_service.py` 增加两类测试：

```python
def test_purchase_runtime_service_reads_default_max_inflight_from_settings():
    service = PurchaseRuntimeService(
        account_repository=FakeAccountRepository([build_account("a1")]),
        settings_repository=FakeSettingsRepository(),
        inventory_snapshot_repository=snapshot_repository,
        execution_gateway_factory=lambda: gateway,
    )
    service.start()
    assert wait_until(lambda: len(gateway.calls) == 1)
```

```python
def test_purchase_runtime_service_applies_updated_max_inflight_after_current_purchase_finishes():
    service = PurchaseRuntimeService(...)
    service.start()
    service.accept_query_hit(...)
    service.apply_purchase_runtime_settings(
        per_batch_ip_fanout_limit=1,
        max_inflight_per_account=2,
    )
    # 在 release 前仍按旧上限；release 后才按新上限放量
```

- [ ] **Step 2: 跑购买 runtime 定向测试，确认红灯**

Run:

```bash
pytest tests/backend/test_purchase_runtime_service.py -k "max_inflight or runtime_settings" -q
```

Expected:

- 至少有读取来源或延迟生效相关失败

- [ ] **Step 3: 写最小实现**

实现要点：

- `PurchaseRuntimeService` 默认 `max_inflight_per_account` 改为 1
- 增加统一的 settings 读取函数，读取：
  - `per_batch_ip_fanout_limit`
  - `max_inflight_per_account`
- 运行时增加 pending settings 状态
- 若当前无在途 dispatch，直接同步：
  - scheduler 的 `max_inflight`
  - dispatch runner 的 `max_concurrent`
- 若当前有在途 dispatch，则先挂 pending，等最后一个 dispatch completion 后再应用
- `PurchaseScheduler` 增加更新账号 inflight 上限的方法
- `_AccountDispatchRunner` 增加更新最大并发的方法
- `main.py` 保持通过 settings repository 驱动，不再依赖隐藏默认 3 的旧语义

- [ ] **Step 4: 跑购买 runtime 定向测试，确认绿灯**

Run:

```bash
pytest tests/backend/test_purchase_runtime_service.py -k "max_inflight or runtime_settings" -q
```

Expected:

- PASS

## Chunk 3: 前端购买设置与提示

### Task 3: 扩展购买设置草稿、请求体与提示文案

**Files:**
- Modify: `app_desktop_web/src/features/purchase-system/components/purchase_settings_panel.jsx`
- Modify: `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js`
- Modify: `app_desktop_web/src/features/purchase-system/purchase_system_page.jsx`
- Modify: `app_desktop_web/src/api/account_center_client.js`
- Modify: `app_desktop_web/src/runtime/runtime_connection_manager.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: 写失败测试，锁定新字段、请求体和等待生效提示**

在前端测试中增加断言：

```js
expect(input).toHaveValue(1);
expect(secondInput).toHaveValue(1);
```

```js
body: {
  per_batch_ip_fanout_limit: 4,
  max_inflight_per_account: 2,
}
```

```js
expect(screen.getByText("已保存，等待当前购买完成后生效")).toBeInTheDocument();
```

- [ ] **Step 2: 跑前端定向测试，确认红灯**

Run:

```bash
npm --prefix app_desktop_web test -- purchase_system_client.test.js purchase_system_page.test.jsx runtime_connection_manager.test.js
```

Expected:

- 至少有新字段缺失或提示缺失相关失败

- [ ] **Step 3: 写最小实现**

实现要点：

- `purchaseSettingsDraft` 补 `max_inflight_per_account`
- 规范化函数、保存校验、保存请求体一起带新字段
- 购买设置面板新增第二个输入框与说明文案
- 若后端返回 pending 生效状态或提示字段，前端展示“等待当前购买完成后生效”
- runtime update 的 store patch 自动带上新字段

- [ ] **Step 4: 跑前端定向测试，确认绿灯**

Run:

```bash
npm --prefix app_desktop_web test -- purchase_system_client.test.js purchase_system_page.test.jsx runtime_connection_manager.test.js
```

Expected:

- PASS

## Chunk 4: 全量回归

### Task 4: 运行闭环验证

**Files:**
- Test: `tests/backend/test_purchase_runtime_service.py`
- Test: `tests/backend/test_runtime_settings_repository.py`
- Test: `tests/backend/test_runtime_settings_routes.py`
- Test: `tests/backend/test_app_bootstrap_route.py`
- Test: `tests/backend/test_runtime_update_websocket.py`
- Test: `app_desktop_web/tests/renderer/purchase_system_client.test.js`
- Test: `app_desktop_web/tests/renderer/purchase_system_page.test.jsx`
- Test: `app_desktop_web/tests/renderer/runtime_connection_manager.test.js`

- [ ] **Step 1: 跑后端验证**

Run:

```bash
pytest tests/backend/test_purchase_runtime_service.py tests/backend/test_runtime_settings_repository.py tests/backend/test_runtime_settings_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q
```

- [ ] **Step 2: 跑前端验证**

Run:

```bash
npm --prefix app_desktop_web test -- purchase_system_client.test.js purchase_system_page.test.jsx runtime_connection_manager.test.js
```

- [ ] **Step 3: 若定向验证全绿，再汇总变更与残余风险**

确认：

- 新默认值为 `1`
- 设置链路读写完整
- runtime 不在购买中途改上限
- 当前购买结束后才应用 pending 设置

