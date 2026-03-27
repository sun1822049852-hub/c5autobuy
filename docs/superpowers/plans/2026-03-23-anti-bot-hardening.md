# Anti-Bot Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 `new_api / fast_api / token` 业务语义的前提下，收敛浏览器态请求契约、硬化 Selenium 登录捕获链、清除凭据泄露点，并补齐反爬回归测试。

**Architecture:** 将所有依赖浏览器态凭据的 C5 请求头、签名生成、cookie 策略与错误归类收口到共享 contract helper；登录链从“页面脚本抓 cookie”为主升级为“DevTools websocket 抓 `userInfo` 响应、页面 monitor、`driver.get_cookies()` 三源合流 + 质量校验”；账号容量与运行时健康判断只修复当前 `token-only` 假阳性，不改成运行时强健康定义，避免 UI 统计语义被意外改写。

**Tech Stack:** Python, asyncio, aiohttp, Selenium, CDP remote debugging, websockets, Node.js-backed `xsign.py`, pytest, git hygiene

**Historical Naming Note:** 本计划撰写时，登录相关模块仍放在 `app_backend/infrastructure/selenium/` 下。当前代码已迁到 `app_backend/infrastructure/browser_runtime/`；本文中的旧路径仅用于保留当时的实施上下文。

---

## 文件结构

- Create: `app_backend/infrastructure/c5/browser_request_contract.py`
  - 统一管理浏览器态凭据快照、`x-sign` 调用、header 顺序、cookie 策略
- Modify: `app_backend/infrastructure/c5/__init__.py`
  - 导出共享 contract helper
- Modify: `app_backend/infrastructure/c5/response_status.py`
  - 扩展 challenge / block page / HTML 错误分类
- Create: `tests/backend/test_browser_request_contract.py`
  - 锁定凭据校验、header 形状、header 顺序和 cookie 策略
- Modify: `app_backend/infrastructure/query/runtime/token_query_executor.py`
  - 改为使用共享 contract helper
- Modify: `tests/backend/test_token_query_executor.py`
  - 锁定 `token` 查询继续复用统一 contract
- Modify: `app_backend/infrastructure/query/collectors/product_detail_fetcher.py`
  - 改为使用共享 contract helper
- Modify: `tests/backend/test_product_detail_fetcher.py`
  - 锁定详情抓取复用统一 contract
- Modify: `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
  - 改为使用共享 contract helper
- Modify: `tests/backend/test_inventory_refresh_gateway.py`
  - 锁定库存刷新复用统一 contract
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
  - 改为使用共享 contract helper
- Modify: `tests/backend/test_purchase_execution_gateway.py`
  - 锁定下单/支付复用统一 contract
- Create: `app_backend/infrastructure/selenium/stealth_scripts.py`
  - 管理 anti-debug 与 stealth 注入脚本，避免散落在 runner 内部
- Create: `app_backend/infrastructure/selenium/network_capture.py`
  - 基于 remote debugging port 读取 `userInfo` 响应与 cookie 线索
- Modify: `app_backend/infrastructure/selenium/selenium_login_runner.py`
  - 接入三源合流、捕获质量打分、关窗解耦、敏感日志清理
- Modify: `tests/backend/test_selenium_login_runner.py`
  - 补充 capture source 优先级、monitor 失效、cookie 缺失、窗口未关等测试
- Modify: `app_backend/application/services/query_mode_capacity_service.py`
  - token 可用性判断改为同时要求 `NC5_accessToken` 与 `NC5_deviceId`
- Modify: `tests/backend/test_query_mode_capacity_service.py`
  - 锁定新的 token 可用性规则
- Modify: `.gitignore`
  - 忽略本地账号快照、请求转储、调试产物
- Modify: `autobuy.py`
  - 只做 legacy 止血：去掉 cookie/token 明文日志，不做行为重构
- Replace: `account/*.json`
  - 用脱敏样例替换真实 cookie/token，保留结构不保留活凭据
- Replace: `调试/api查询.py`
  - 用环境变量占位替代硬编码 API key
- Replace: `调试/xsigntest.py`
  - 用环境变量占位替代硬编码 token
- Modify: `README.md`
  - 更新登录/浏览器态契约与本地调试说明
- Verify: `app_backend/api/routes/query_configs.py`
  - 明确 `available_account_count` 仍是“满足最小契约的可配置账号数”，不是运行时健康数

## 执行边界

- **Workstream A: 仓库止血**
  - 只处理已提交凭据、legacy 明文日志、调试脚本硬编码值
  - 必须单独 commit，禁止与 backend 行为重构混在同一提交
- **Workstream B: Backend 反爬重构**
  - 只覆盖 `app_backend/` 主链与其测试
  - 允许在 Workstream A 合并后开始
- **Legacy 范围说明**
  - `autobuy.py` 本计划只做敏感日志治理
  - 不在本计划中继续重构 legacy 登录、查询、购买逻辑

## Chunk 1: 凭据卫生与仓库止血

### Task 1: 清理被版本控制的活凭据与本地调试泄露点

**Files:**
- Modify: `.gitignore`
- Modify: `autobuy.py`
- Replace: `account/account_1003446248.json`
- Replace: `account/account_1003936745.json`
- Replace: `account/account_1003949003.json`
- Replace: `account/account_1004008548.json`
- Replace: `account/account_1004008551.json`
- Replace: `调试/api查询.py`
- Replace: `调试/xsigntest.py`
- Verify: `git ls-files -- account 调试`

- [ ] **Step 1: 盘点当前被 git 跟踪的敏感文件**

Run: `git ls-files -- account 调试`
Expected: 能看到当前被跟踪的账号快照和调试脚本。

- [ ] **Step 2: 用脱敏占位替换账号快照中的 live cookie/token**

```json
{
  "remark_name": "sample-account",
  "cookie": "NC5_accessToken=[REDACTED]; NC5_deviceId=[REDACTED]"
}
```

- [ ] **Step 3: 把调试脚本改成环境变量输入，不再硬编码凭据**

```python
API_KEY = os.environ["C5_API_KEY"]
TOKEN = os.environ["C5_ACCESS_TOKEN"]
```

- [ ] **Step 4: 更新 `.gitignore`，忽略本地账号导出、请求转储和调试样本**

```gitignore
account/*.local.json
调试/request.json
调试/response_*.txt
调试/*.local.py
```

- [ ] **Step 5: 运行敏感字符串搜索确认止血**

Run: `rg -n "NC5_accessToken=|NC5_crossAccessToken=|eyJ0eXAiOiJKV1Qi|API_KEY = \"" account 调试`
Expected: 只剩脱敏占位，不再出现 live token 或硬编码 key。

- [ ] **Step 6: 移除 legacy 明文 cookie 日志，但不改 legacy 行为**

```python
console.log("Cookie:", "[REDACTED]")
```

- [ ] **Step 7: 检查索引状态，确认样例文件仍存在但字段已脱敏**

Run: `git diff --cached -- account 调试 autobuy.py`
Expected: 只出现脱敏替换和日志打码，不出现整目录误删。

- [ ] **Step 8: Commit**

```bash
git add .gitignore account 调试 autobuy.py
git commit -m "chore: redact tracked credentials and legacy debug leaks"
```

## Chunk 2: 浏览器态请求契约收口

### Task 2: 先写共享 contract 的失败测试

**Files:**
- Create: `tests/backend/test_browser_request_contract.py`
- Create: `app_backend/infrastructure/c5/browser_request_contract.py`

- [ ] **Step 1: 写失败测试，锁定凭据快照必须同时要求 token 和 device**

```python
def test_browser_request_contract_requires_token_and_device_id():
    account = build_account(cookie_raw="NC5_accessToken=token-only")
    with pytest.raises(ValueError, match="NC5_deviceId"):
        BrowserCredentialSnapshot.from_runtime_account(RuntimeAccountAdapter(account))
```

- [ ] **Step 2: 写失败测试，锁定 POST 请求头顺序与字段**

```python
def test_browser_request_contract_builds_expected_post_headers():
    contract = BrowserRequestContract(...)
    headers = contract.build_headers(...)
    assert list(headers.keys())[:6] == ["Host", "User-Agent", "Accept", "Accept-Language", "Accept-Encoding", "Referer"]
    assert headers["Cookie"] == account.cookie_raw
    assert headers["x-sign"] == "fake-sign"
    assert headers["x-device-id"] == "device-1"
```

- [ ] **Step 3: 写失败测试，锁定 GET 场景和 cookie 策略默认走 exact**

```python
def test_browser_request_contract_uses_exact_cookie_by_default():
    headers = contract.build_headers(method="GET", ...)
    assert headers["Cookie"] == "foo=bar; _csrf=abc%3D"
```

- [ ] **Step 4: 运行新测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_browser_request_contract.py -q`
Expected: FAIL，提示共享 contract 尚未实现。

### Task 3: 实现共享 contract 并迁移四条浏览器态请求链

**Files:**
- Create: `app_backend/infrastructure/c5/browser_request_contract.py`
- Modify: `app_backend/infrastructure/c5/__init__.py`
- Modify: `app_backend/infrastructure/query/runtime/token_query_executor.py`
- Modify: `app_backend/infrastructure/query/collectors/product_detail_fetcher.py`
- Modify: `app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py`
- Modify: `app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py`
- Modify: `tests/backend/test_token_query_executor.py`
- Modify: `tests/backend/test_product_detail_fetcher.py`
- Modify: `tests/backend/test_inventory_refresh_gateway.py`
- Modify: `tests/backend/test_purchase_execution_gateway.py`

- [ ] **Step 1: 实现凭据快照与 `x-sign` 调用封装**

```python
@dataclass(frozen=True, slots=True)
class BrowserCredentialSnapshot:
    access_token: str
    device_id: str
    cookie_raw: str
```

- [ ] **Step 2: 实现统一 header builder，保留现有顺序和字段**

```python
class BrowserRequestContract:
    def build_headers(self, *, api_path: str, method: str, referer_url: str, content_type: str | None) -> OrderedDict[str, str]:
        ...
```

- [ ] **Step 3: 让 `token_query_executor.py` 改为调用共享 contract**

```python
headers = self._contract.build_headers(
    api_path=self.API_PATH,
    method="POST",
    referer_url=query_item.product_url,
    content_type="application/json",
)
```

- [ ] **Step 4: 让详情抓取、库存刷新、下单支付都改为复用同一个 contract**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_token_query_executor.py tests/backend/test_product_detail_fetcher.py tests/backend/test_inventory_refresh_gateway.py tests/backend/test_purchase_execution_gateway.py -q`
Expected: 先 FAIL，迁移完成后 PASS。

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/c5 app_backend/infrastructure/query/runtime/token_query_executor.py app_backend/infrastructure/query/collectors/product_detail_fetcher.py app_backend/infrastructure/purchase/runtime/inventory_refresh_gateway.py app_backend/infrastructure/purchase/runtime/purchase_execution_gateway.py tests/backend/test_browser_request_contract.py tests/backend/test_token_query_executor.py tests/backend/test_product_detail_fetcher.py tests/backend/test_inventory_refresh_gateway.py tests/backend/test_purchase_execution_gateway.py
git commit -m "refactor: centralize browser-mode c5 request contract"
```

## Chunk 3: Selenium 登录捕获硬化

### Task 4: 先验证 DevTools transport 能否稳定拿到目标响应

**Files:**
- Create: `app_backend/infrastructure/selenium/network_capture.py`
- Modify: `tests/backend/test_selenium_login_runner.py`

- [ ] **Step 1: 写失败测试，锁定 debug port 可解析 websocket endpoint**

```python
async def test_network_capture_resolves_websocket_url_from_debug_port():
    client = NetworkCaptureClient(debug_port=9222, http_get=fake_http_get, websocket_factory=fake_ws)
    assert await client.resolve_target_websocket_url() == "ws://127.0.0.1/devtools/page/target-1"
```

- [ ] **Step 2: 写失败测试，锁定只抓 `/api/v1/user/v2/userInfo` 的响应体**

```python
async def test_network_capture_extracts_userinfo_response_body_only():
    payload = await client.capture_userinfo_payload(timeout_seconds=1.0)
    assert payload["response"] == '{"success": true, "data": {"personalData": {"userId": "10001"}}}'
```

- [ ] **Step 3: 运行 transport 测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py -k "network_capture" -q`
Expected: FAIL，提示 `NetworkCaptureClient` 尚未实现。

### Task 5: 先写 runner 的失败测试，锁定三源合流与关窗解耦

**Files:**
- Create: `app_backend/infrastructure/selenium/stealth_scripts.py`
- Create: `app_backend/infrastructure/selenium/network_capture.py`
- Modify: `app_backend/infrastructure/selenium/selenium_login_runner.py`
- Modify: `tests/backend/test_selenium_login_runner.py`

- [ ] **Step 1: 写失败测试，锁定 capture source 优先级为 network > monitor > browser cookies**

```python
async def test_selenium_login_runner_prefers_network_capture_over_monitor_cookie():
    result = await runner.run(proxy_url="direct")
    assert result["capture_source"] == "network"
    assert "NC5_accessToken=token-network" in result["cookie_raw"]
```

- [ ] **Step 2: 写失败测试，锁定“已捕获凭据”与“浏览器关闭”解耦**

```python
async def test_selenium_login_runner_marks_capture_before_browser_close():
    states = []
    result = await runner.run(proxy_url="direct", emit_state=states.append)
    assert "captured_login_info" in states
    assert result["capture_quality"]["contains_device_id"] is True
```

- [ ] **Step 3: 写失败测试，锁定 monitor 注入失败后仍可通过 browser cookies 完成**

```python
async def test_selenium_login_runner_falls_back_when_monitor_script_injection_fails():
    ...
    assert result["capture_source"] == "browser_cookies"
```

- [ ] **Step 4: 运行 runner 测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py -q`
Expected: FAIL，提示 capture source / quality / network capture 逻辑未实现。

### Task 6: 实现 stealth 脚本、network capture 和 runner 收口

**Files:**
- Create: `app_backend/infrastructure/selenium/stealth_scripts.py`
- Create: `app_backend/infrastructure/selenium/network_capture.py`
- Modify: `app_backend/infrastructure/selenium/selenium_login_runner.py`
- Modify: `tests/backend/test_selenium_login_runner.py`

- [ ] **Step 1: 把 anti-debug 与 stealth JS 从 runner 中拆到 `stealth_scripts.py`**

```python
def build_login_monitor_script() -> str:
    return build_anti_debug_script() + build_basic_stealth_script() + build_userinfo_monitor_script()
```

- [ ] **Step 2: 实现最小 network capture 客户端，钉死 transport 为 `json/version + DevTools websocket`**

```python
class NetworkCaptureClient:
    async def resolve_target_websocket_url(self) -> str:
        ...

    async def capture_userinfo_payload(self, *, timeout_seconds: float) -> dict[str, object] | None:
        ...
```

- [ ] **Step 3: 在 `BrowserSession` 中暴露 `debug_port`，并同步修改默认浏览器创建测试桩**

```python
@dataclass(slots=True)
class BrowserSession:
    driver: Any
    debug_port: int | None = None
```

- [ ] **Step 4: 在 `tests/backend/test_selenium_login_runner.py` 中补齐 `BrowserSession(debug_port=...)` 和 `_create_default_browser()` 回归断言**

- [ ] **Step 5: 在 runner 中实现三源合流和 capture quality**

```python
capture = first_non_null([network_payload, monitor_payload, browser_cookie_payload])
result["capture_source"] = capture.source
result["capture_quality"] = {"contains_token": ..., "contains_device_id": ..., "cookie_count": ...}
```

- [ ] **Step 6: 删除或打码任何 cookie/token 明文日志**

Run: `rg -n "Cookie:'|document.cookie|NC5_accessToken|NC5_deviceId" app_backend/infrastructure/selenium autobuy.py`
Expected: backend runner 中不再出现明文 cookie 输出。

- [ ] **Step 7: 复跑 runner 与登录任务相关测试**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_selenium_login_runner.py tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app_backend/infrastructure/selenium tests/backend/test_selenium_login_runner.py tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py
git commit -m "feat: harden selenium login capture pipeline"
```

## Chunk 4: 错误分类与账号健康规则收口

### Task 7: 先写 challenge 分类和容量规则的失败测试

**Files:**
- Modify: `app_backend/infrastructure/c5/response_status.py`
- Modify: `tests/backend/test_c5_response_status_helper.py`
- Modify: `app_backend/application/services/query_mode_capacity_service.py`
- Modify: `tests/backend/test_query_mode_capacity_service.py`

- [ ] **Step 1: 写失败测试，锁定 challenge HTML 与普通 HTML 错误页分开处理**

```python
def test_c5_status_helper_marks_html_challenge_as_forbidden():
    error = classify_c5_response_error(status=200, text="<html><title>Just a moment...</title></html>")
    assert error == "HTTP 403 Forbidden"


def test_c5_status_helper_keeps_generic_html_page_out_of_auth_invalid():
    error = classify_c5_response_error(status=200, text="<html><title>Maintenance</title></html>")
    assert error == "HTTP 200 HTML Error Page"


def test_c5_status_helper_keeps_5xx_proxy_html_as_http_error():
    error = classify_c5_response_error(status=503, text="<html><title>Bad gateway</title></html>")
    assert error == "HTTP 503 请求失败"
```

- [ ] **Step 2: 写失败测试，锁定 token 容量语义只修最小契约，不引入运行时健康定义**

```python
def test_query_mode_capacity_service_requires_device_id_for_token_accounts():
    service = QueryModeCapacityService(FakeAccountRepository([build_account("token-only", cookie_raw="NC5_accessToken=token-1")]))
    assert service.get_summary()["modes"]["token"]["available_account_count"] == 0
```

- [ ] **Step 3: 运行测试确认失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_c5_response_status_helper.py tests/backend/test_query_mode_capacity_service.py -q`
Expected: FAIL，提示旧 helper 仍把 challenge 当普通 200，容量仍只检查 access token。

### Task 8: 实现 challenge 分类与最小 token 契约校验

**Files:**
- Modify: `app_backend/infrastructure/c5/response_status.py`
- Modify: `app_backend/application/services/query_mode_capacity_service.py`
- Modify: `tests/backend/test_c5_response_status_helper.py`
- Modify: `tests/backend/test_query_mode_capacity_service.py`
- Verify: `app_backend/api/routes/query_configs.py`

- [ ] **Step 1: 在 `response_status.py` 仅把 challenge HTML 归类为 auth invalid，普通 HTML 保持 generic error**

```python
if status == 200 and any(marker in normalized for marker in ("just a moment", "verify you are human", "__cf_chl", "captcha")):
    return "HTTP 403 Forbidden"
if status == 200 and normalized.startswith("<html"):
    return "HTTP 200 HTML Error Page"
```

- [ ] **Step 2: 在容量服务中只修复 `token-only` 假阳性，保留现有 `available_account_count` 语义**

```python
return "NC5_accessToken=" in cookie_raw and "NC5_deviceId=" in cookie_raw
```

- [ ] **Step 3: 复跑 helper、容量、查询配置路由回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_c5_response_status_helper.py tests/backend/test_query_mode_capacity_service.py tests/backend/test_query_config_routes.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py -q`
Expected: PASS

- [ ] **Step 4: 在 README 中补一条容量定义说明，避免后续再把容量数当健康数**

- [ ] **Step 5: Commit**

```bash
git add app_backend/infrastructure/c5/response_status.py app_backend/application/services/query_mode_capacity_service.py tests/backend/test_c5_response_status_helper.py tests/backend/test_query_mode_capacity_service.py tests/backend/test_query_runtime_service.py tests/backend/test_query_runtime_routes.py
git commit -m "fix: align c5 auth error and token capacity rules"
```

## Chunk 5: 文档与全量回归

### Task 9: 更新文档并跑反爬回归矩阵

**Files:**
- Modify: `README.md`
- Optionally Modify: `docs/superpowers/references/2026-03-19-autobuy-backend-semantic-drift-reference.md`

- [ ] **Step 1: 更新 README，写明本地账号文件必须使用脱敏样例与环境变量**

```markdown
- 账号 cookie/token 不得提交到仓库
- 调试脚本必须通过环境变量读取敏感信息
- 浏览器态接口共用 `browser_request_contract.py`
```

- [ ] **Step 2: 如有必要，更新 semantic drift reference，补写新的 capture source 和 token/device 健康规则**

- [ ] **Step 3: 运行反爬相关全套回归**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_browser_request_contract.py tests/backend/test_token_query_executor.py tests/backend/test_product_detail_fetcher.py tests/backend/test_inventory_refresh_gateway.py tests/backend/test_purchase_execution_gateway.py tests/backend/test_selenium_login_runner.py tests/backend/test_c5_response_status_helper.py tests/backend/test_query_mode_capacity_service.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`
Expected: PASS

- [ ] **Step 4: 运行全量测试**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/references/2026-03-19-autobuy-backend-semantic-drift-reference.md
git commit -m "docs: document anti-bot hardening contract"
```

## 完成定义

- 仓库中不再跟踪 live cookie、token、API key
- 浏览器态四条请求链只保留一份 contract 实现
- 登录链支持 `network > monitor > browser cookies` 的捕获优先级
- token 可用性判断与真实运行时前置条件一致
- `200 + HTML challenge` 不再被误判成 JSON 错误
- 反爬专项测试与全量测试全部通过
