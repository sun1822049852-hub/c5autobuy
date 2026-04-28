# Diagnostics Push Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 diagnostics 页面改为“首次可见快照 + 专用 websocket push + 重显 resync”，彻底替掉现有 diagnostics polling。

**Architecture:** 保留 `GET /diagnostics/sidebar` 作为 truth source 和 resync 入口，不复用现有 `/ws/runtime`。新增 diagnostics 专用 websocket 路由，只在页面前台可见时连接；后端每次收到 runtime/account/login-task 变化信号后，重算完整 diagnostics 快照并推给前端。前端 hook 负责一次首屏快照、visible-only 连接、hidden 断开、重显先 resync 再重连，且不再对 diagnostics 做 hidden warmup 或 steady-state polling。

**Tech Stack:** React 19, FastAPI, WebSocket, Vitest, Testing Library, pytest, Python 3.11

---

## Scope

### In Scope
- diagnostics 页面专用 websocket push
- diagnostics 首次可见只拉一次 `/diagnostics/sidebar`
- 页面隐藏时断开 push，不再 hidden polling / hidden warmup
- 页面重新可见时先做一次 `/diagnostics/sidebar` resync，再重连 push
- 保留现有 diagnostics 快照语义：查询/购买/登录任务结构与错误保留口径不降级

### Out Of Scope
- 不重做已完成的 embedded runtime push
- 不复用或改造 `/ws/runtime`
- 不改 `/health -> ready=true` 语义
- 不把 diagnostics 扩成全局统一推送重构
- 不回退到 polling fallback

## File Map

- Modify: `app_backend/workers/manager/task_manager.py`
  - 为 diagnostics websocket 增加“任意登录任务变化”订阅能力，避免前端继续轮询登录任务
- Create: `app_backend/api/websocket/diagnostics.py`
  - diagnostics 专用 websocket 路由 `/ws/diagnostics/sidebar`
- Modify: `app_backend/main.py`
  - 注册 diagnostics websocket router
- Modify: `app_backend/api/routes/diagnostics.py`
  - 如有必要，抽出共享的 snapshot builder 取用方式，保持 HTTP route 与 websocket 共用同一 truth source
- Modify: `app_backend/application/use_cases/get_sidebar_diagnostics.py`
  - 如有必要，只做读路径收口，确保 HTTP 和 websocket 推送产出的快照结构完全一致
- Create: `tests/backend/test_diagnostics_websocket.py`
  - 锁死 diagnostics websocket 对 runtime change / login task change 的推送契约
- Modify: `app_desktop_web/src/api/account_center_client.js`
  - 新增 diagnostics websocket URL builder 与 `watchSidebarDiagnosticsUpdates()`
- Modify: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
  - 从 polling hook 改成 resync + websocket hook
- Modify: `app_desktop_web/src/App.jsx`
  - diagnostics 页面不再 hidden warmup；只在 diagnostics 页 active 时启用 hook
- Modify: `app_desktop_web/tests/renderer/diagnostics_client.test.js`
  - 锁死 diagnostics client 的 websocket 入口
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`
  - 锁死 visible-only push、hidden disconnect、visible resync 行为
- Modify: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`
  - 锁死 diagnostics 不参与 hidden warmup

## Chunk 1: Backend Push Contract

### Task 1: Add failing websocket route tests first

**Files:**
- Create: `tests/backend/test_diagnostics_websocket.py`

- [ ] **Step 1: Write the failing runtime-driven websocket test**

```python
def test_diagnostics_websocket_streams_snapshot_after_runtime_update(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/diagnostics/sidebar") as websocket:
            app.state.runtime_update_hub.publish(
                event="query_runtime.updated",
                payload={"running": True},
            )
            payload = websocket.receive_json()

    assert payload["summary"]["query_running"] is True
    assert payload["query"]["config_name"] == "查询配置A"
```

- [ ] **Step 2: Write the failing login-task websocket test**

```python
def test_diagnostics_websocket_streams_snapshot_after_login_task_change(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/diagnostics/sidebar") as websocket:
            task = app.state.task_manager.create_task(task_type="login", message="创建任务")
            app.state.task_manager.set_state(task.task_id, "waiting_for_scan", message="等待扫码")
            payload = websocket.receive_json()

    assert payload["login_tasks"]["recent_tasks"][0]["task_id"] == task.task_id
    assert payload["login_tasks"]["recent_tasks"][0]["state"] == "waiting_for_scan"
```

- [ ] **Step 3: Run the focused backend test and verify RED**

Run:

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest `
  tests/backend/test_diagnostics_websocket.py -q
```

Expected:
- websocket route `/ws/diagnostics/sidebar` still不存在，测试失败

- [ ] **Step 4: Implement the dedicated diagnostics websocket**

Rules:
- 不复用 `/ws/runtime`
- websocket payload 直接推完整 diagnostics snapshot，不推增量 patch
- snapshot 来源必须复用现有 `GetSidebarDiagnosticsUseCase`
- runtime/account/login-task 的变化信号只负责触发“重算并推送”，不得在主链同步热路径里现算 diagnostics

- [ ] **Step 5: Re-run backend websocket tests and confirm GREEN**

## Chunk 2: Frontend Client And Hook Red First

### Task 2: Add failing diagnostics client websocket coverage

**Files:**
- Modify: `app_desktop_web/tests/renderer/diagnostics_client.test.js`
- Modify: `app_desktop_web/src/api/account_center_client.js`

- [ ] **Step 1: Write the failing client test**

```js
it("streams sidebar diagnostics from the dedicated websocket endpoint", async () => {
  const client = createAccountCenterClient({
    apiBaseUrl: "http://127.0.0.1:8123",
    WebSocketImpl: FakeWebSocket,
  });

  const nextSnapshot = client.watchSidebarDiagnosticsUpdates().next();

  expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8123/ws/diagnostics/sidebar");
  FakeWebSocket.instances[0].emit(buildDiagnosticsSnapshot());
  await expect(nextSnapshot).resolves.toEqual(
    expect.objectContaining({ value: expect.objectContaining({ updated_at: expect.any(String) }) }),
  );
});
```

- [ ] **Step 2: Run focused client test and verify RED**

Run:

```powershell
npm --prefix app_desktop_web test -- tests/renderer/diagnostics_client.test.js --run
```

Expected:
- `watchSidebarDiagnosticsUpdates()` 尚不存在

- [ ] **Step 3: Implement the minimal client support**

Rules:
- URL 固定为 `/ws/diagnostics/sidebar`
- diagnostics websocket 不允许像 task stream 那样回退到 steady-state polling
- 若 `WebSocket` 不可用，只允许停在快照态/等待 resync，不得静默恢复旧 polling

- [ ] **Step 4: Re-run focused client test and confirm GREEN**

## Chunk 3: Visible-Only Diagnostics Hook

### Task 3: Add failing diagnostics page behavior tests

**Files:**
- Modify: `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx`
- Modify: `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`
- Modify: `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js`
- Modify: `app_desktop_web/src/App.jsx`

- [ ] **Step 1: Write the failing visible-only push test**

```jsx
it("loads diagnostics once, then switches to websocket push instead of steady-state polling", async () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "通用诊断" }));

  await screen.findByRole("complementary", { name: "通用诊断面板" });
  expect(countDiagnosticsFetches()).toBe(1);
  expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8123/ws/diagnostics/sidebar");
});
```

- [ ] **Step 2: Write the failing hidden/visible resync test**

```jsx
it("disconnects while hidden and resyncs once before reconnecting when visible again", async () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "通用诊断" }));
  await screen.findByRole("complementary", { name: "通用诊断面板" });

  setVisibilityState("hidden");
  fireEvent(document, new Event("visibilitychange"));
  expect(FakeWebSocket.instances[0].closed).toBe(true);
  expect(countDiagnosticsFetches()).toBe(1);

  setVisibilityState("visible");
  fireEvent(document, new Event("visibilitychange"));
  expect(countDiagnosticsFetches()).toBe(2);
  expect(FakeWebSocket.instances).toHaveLength(2);
});
```

- [ ] **Step 3: Write the failing keepalive warmup test**

```jsx
it("does not warm diagnostics while the diagnostics page stays hidden", async () => {
  render(<App />);
  await waitFor(() => {
    expect(countCalls(harness.calls, "/diagnostics/sidebar")).toBe(0);
  });
});
```

- [ ] **Step 4: Run focused renderer tests and verify RED**

Run:

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/diagnostics_sidebar.test.jsx `
  tests/renderer/app_page_keepalive.test.jsx --run
```

Expected:
- diagnostics 仍在用 polling hook
- hidden warmup 仍会触发 `/diagnostics/sidebar`
- diagnostics 页面还不会建立专用 websocket

- [ ] **Step 5: Implement the hook rewrite**

Rules:
- 首次 visible：`GET /diagnostics/sidebar` 一次，然后连 websocket
- steady-state：只吃 websocket 推送
- hidden：立即断开 websocket，不发 hidden fetch
- visible again：先 resync，再重连 websocket
- 保留现有本地错误/异常账号保留语义；recent events 仍按最新快照替换

- [ ] **Step 6: Re-run focused renderer tests and confirm GREEN**

## Chunk 4: Final Verification

### Task 4: Focused verification and session log

**Files:**
- Modify: `docs/agent/session-log.md`

- [ ] **Step 1: Run backend diagnostics tests**

```powershell
C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest `
  tests/backend/test_diagnostics_routes.py `
  tests/backend/test_diagnostics_websocket.py -q
```

- [ ] **Step 2: Run renderer diagnostics tests**

```powershell
npm --prefix app_desktop_web test -- `
  tests/renderer/diagnostics_client.test.js `
  tests/renderer/diagnostics_sidebar.test.jsx `
  tests/renderer/app_page_keepalive.test.jsx --run
```

- [ ] **Step 3: Manual smoke**

Checklist:
- 首次打开 diagnostics 只打一条 `/diagnostics/sidebar`
- 前台停留时不再 steady-state polling
- hidden 后 diagnostics websocket 断开
- 重显时先 resync，再恢复实时更新
- query/purchase/login-task 的快照都能通过专用 push 刷新

- [ ] **Step 4: Update `docs/agent/session-log.md` with evidence**

## Notes For Executor

- 当前工作树已有 embedded runtime push 未提交改动；本计划不得重做或覆盖那批已完成实现。
- diagnostics push 不得复用 `/ws/runtime`，但后端可以复用现有 runtime/account/task 变化信号来触发 diagnostics 快照重算。
- hidden diagnostics 不仅不能 steady-state polling，也不应再参与 hidden warmup。

Plan complete and saved to `docs/superpowers/plans/2026-04-28-diagnostics-push.md`.
