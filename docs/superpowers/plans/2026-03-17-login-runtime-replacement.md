# Login Runtime Replacement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变扫码登录体验、任务状态流、冲突处理和账号保存行为的前提下，把登录底层执行链路从 legacy `autobuy.py` 中剥离出来，接入新架构自己的 Selenium 登录运行器。

**Architecture:** 保留现有 `login_adapter.run_login(...) -> LoginCapture` 对外合同不变，只替换 adapter 内部的执行来源。新增一个新的 Selenium 登录运行器，承接浏览器启动、代理配置、监控脚本、扫码成功判定、用户信息提取、cookie 提取以及 `NC5_deviceId` 重写逻辑；登录任务、冲突处理和持久化逻辑不动。

**Tech Stack:** Python, asyncio, Selenium, pytest

**Historical Naming Note:** 本计划中的 `app_backend/infrastructure/selenium/` 和 `SeleniumLoginAdapter` 都是当时命名。当前代码里，活跃登录链已迁到 `app_backend/infrastructure/browser_runtime/`，适配器现名为 `BrowserLoginAdapter`。

---

## 文件结构

- Create: `app_backend/infrastructure/selenium/selenium_login_runner.py`
  - 新的 Selenium 登录运行器，负责浏览器生命周期、监控脚本、扫码成功判定和结果提取
- Modify: `app_backend/infrastructure/selenium/login_adapter.py`
  - 保持 `LoginCapture` 与 `run_login(...)` 合同不变，去掉对 `autobuy.py` 的依赖，改为调用新运行器
- Modify: `app_backend/main.py`
  - 如果需要，保持 app 默认仍注入同一个 adapter 类，但其内部不再依赖 legacy
- Create: `tests/backend/test_selenium_login_runner.py`
  - 覆盖运行器主流程、取消、超时、cookie 回退和 `NC5_deviceId` 规则
- Modify: `tests/backend/test_login_adapter_contract.py`
  - 锁定 adapter 契约不变，并验证不再需要 legacy loader
- Verify: `tests/backend/test_login_task_flow.py`
  - 确认登录成功后的任务流与账号落库不回归
- Verify: `tests/backend/test_login_conflict_flow.py`
  - 确认 conflict 流不回归
- Verify: `tests/backend/test_account_center_smoke.py`
  - 确认 app 默认登录适配器与账号中心链路不回归
- Modify: `README.md`
  - 更新登录链路去 legacy 进度

## Chunk 1: 登录运行器单测先行

### Task 1: 写 `SeleniumLoginRunner` 的失败测试

**Files:**
- Create: `tests/backend/test_selenium_login_runner.py`
- Create: `app_backend/infrastructure/selenium/selenium_login_runner.py`

- [ ] **Step 1: 写失败测试，锁定“成功获取用户信息 + cookie + 重写 deviceId”主路径**

```python
async def test_selenium_login_runner_returns_capture_after_browser_closed():
    driver = FakeDriver(
        current_url="https://www.c5game.com/user/user/",
        execute_script_results=[request_data_payload],
        browser_cookies=[],
        alive_sequence=[True, False],
    )
    runner = SeleniumLoginRunner(driver_factory=lambda **kwargs: driver)
    result = await runner.run(proxy_url="direct", emit_state=collector)
    assert result["user_info"]["userId"] == "10001"
    assert "NC5_deviceId=" in result["cookie_raw"]
    assert result["cookie_raw"] != original_cookie
```

- [ ] **Step 2: 写失败测试，锁定状态顺序与取消/超时语义**

```python
async def test_selenium_login_runner_emits_scan_capture_and_wait_close_states():
    ...
    assert states == ["waiting_for_scan", "captured_login_info", "waiting_for_browser_close"]


async def test_selenium_login_runner_returns_cancelled_when_browser_closed_before_login():
    ...
    assert result["success"] is False
    assert result["error"] == "用户取消了登录"


async def test_selenium_login_runner_returns_timeout_when_login_not_completed():
    ...
    assert result["error"] == "登录失败或超时"
```

- [ ] **Step 3: 写失败测试，锁定兜底提取、cookie 回退和 `NC5_deviceId` 规则**

```python
async def test_selenium_login_runner_falls_back_to_direct_user_info_extraction():
    ...
    assert result["user_info"]["userId"] == "10001"


async def test_selenium_login_runner_falls_back_to_browser_cookies_when_monitor_cookie_missing():
    ...
    assert "NC5_accessToken=token-1" in result["cookie_raw"]


async def test_selenium_login_runner_fails_when_cookie_missing_device_id():
    ...
    assert result["success"] is False
    assert result["error"] == "无法获取NC5_deviceId"
```

- [ ] **Step 4: 写失败测试，锁定代理配置参数传递**

```python
def test_selenium_login_runner_passes_proxy_url_to_browser_factory():
    ...
    assert captured["proxy_url"] == "http://127.0.0.1:8888"
```

- [ ] **Step 5: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py -q`
Expected: FAIL，提示 `SeleniumLoginRunner` 不存在或行为未实现

## Chunk 2: 最小实现登录运行器

### Task 2: 实现 `SeleniumLoginRunner`

**Files:**
- Create: `app_backend/infrastructure/selenium/selenium_login_runner.py`
- Create: `tests/backend/test_selenium_login_runner.py`

- [ ] **Step 1: 实现运行器返回结构和状态发射骨架**

```python
class SeleniumLoginRunner:
    async def run(self, *, proxy_url: str | None, emit_state) -> dict[str, object]:
        await _safe_emit(emit_state, "waiting_for_scan")
        ...
```

- [ ] **Step 2: 实现监控数据解析与用户信息提取**

```python
def _extract_user_info_from_monitor_payload(payload: dict[str, object]) -> dict[str, object] | None:
    ...


async def _extract_user_info_directly(self, driver) -> dict[str, object] | None:
    ...
```

- [ ] **Step 3: 实现 cookie 提取和 `NC5_deviceId` 重写**

```python
def _rewrite_device_id(cookie_raw: str, *, now_ms: int, random_part: int) -> str:
    ...
    if "NC5_deviceId" not in cookie_dict:
        raise RuntimeError("无法获取NC5_deviceId")
```

- [ ] **Step 4: 实现取消/超时/成功路径**

```python
if browser_closed_before_login:
    return {"success": False, "error": "用户取消了登录"}
if timed_out:
    return {"success": False, "error": "登录失败或超时"}
```

- [ ] **Step 5: 复跑运行器测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py -q`
Expected: PASS

## Chunk 3: 切换 adapter 到新运行器

### Task 3: 让 `login_adapter` 不再依赖 `autobuy.py`

**Files:**
- Modify: `app_backend/infrastructure/selenium/login_adapter.py`
- Modify: `tests/backend/test_login_adapter_contract.py`

- [ ] **Step 1: 改写 adapter 契约测试，锁定合同不变但不再需要 legacy loader**

```python
async def test_login_adapter_returns_c5_payload_from_runner():
    ...
    assert result.c5_user_id == "10001"
    assert result.cookie_raw == "foo=bar"
```

- [ ] **Step 2: 新增 adapter 红灯测试，锁定默认 runner 为新运行器**

```python
def test_login_adapter_uses_selenium_login_runner_by_default():
    adapter = SeleniumLoginAdapter()
    assert isinstance(adapter._login_runner, SeleniumLoginRunner)
```

- [ ] **Step 3: 运行 adapter 测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_adapter_contract.py -q`
Expected: FAIL，提示 adapter 仍加载 legacy 模块或默认 runner 未切换

- [ ] **Step 4: 修改 adapter，移除 `_load_legacy_autobuy_module()` 路径**

```python
from app_backend.infrastructure.selenium.selenium_login_runner import SeleniumLoginRunner
...
self._login_runner = login_runner or SeleniumLoginRunner().run
```

- [ ] **Step 5: 复跑 adapter 测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_adapter_contract.py -q`
Expected: PASS

## Chunk 4: 登录任务流回归

### Task 4: 确认登录任务、冲突处理和账号中心不回归

**Files:**
- Verify: `tests/backend/test_login_task_flow.py`
- Verify: `tests/backend/test_login_conflict_flow.py`
- Verify: `tests/backend/test_account_center_smoke.py`

- [ ] **Step 1: 运行登录任务流回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_task_flow.py -q`
Expected: PASS

- [ ] **Step 2: 运行登录冲突流回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_conflict_flow.py -q`
Expected: PASS

- [ ] **Step 3: 运行账号中心烟测**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_center_smoke.py -q`
Expected: PASS

- [ ] **Step 4: 只有测试失败时才做最小修正**

```python
if current_account.c5_user_id and current_account.c5_user_id != capture.c5_user_id:
    ...
```

- [ ] **Step 5: 复跑登录相关回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py tests/backend/test_account_center_smoke.py -q`
Expected: PASS

## Chunk 5: 最终验证

### Task 5: 整体验证登录迁移不破外部合同

**Files:**
- Modify: `README.md`
- Verify only

- [ ] **Step 1: 更新 README 中登录链路去 legacy 进度**

```markdown
- 登录执行链路已从 `autobuy.py` 中剥离
- 账号中心后端运行时已不再依赖 legacy 登录管理器
```

- [ ] **Step 2: 运行登录迁移相关定向测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py tests/backend/test_account_center_smoke.py -q`
Expected: PASS

- [ ] **Step 3: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 4: 汇报结果，只报告已验证内容**

注：

- 本计划不包含 git 提交
- `SeleniumLoginAdapter` 命名清理已在后续完成
