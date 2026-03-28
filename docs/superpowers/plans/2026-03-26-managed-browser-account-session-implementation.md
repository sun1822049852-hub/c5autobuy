# Managed Browser Account Session Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地第一版受管浏览器登录链，使登录始终使用全新受管浏览器会话、登录成功后强制刷新验真、并把账号会话资产以加密 bundle 形式按账号持久化保存。

**Architecture:** 本计划只实现 spec 的 phase 1-2 加上必要的冲突归属/删除清理闭环，不提前做完整“浏览器恢复 UI”。后端新增 `AccountSessionBundle` 元数据 + 加密负载仓储、`LoginExecutionResult` 内部结果对象和受管浏览器 runtime/seed/session 三件套；现有外部 HTTP API、任务状态名和前端交互保持不变，Node 侧只负责把应用私有目录传给 Python backend。

**Tech Stack:** Python, FastAPI, SQLite, SQLAlchemy, ctypes/Windows DPAPI, Selenium, pytest, Node.js, Vitest

**Historical Naming Note:** 本计划撰写时，相关模块仍记在 `app_backend/infrastructure/selenium/` 下；当前代码中这些活跃模块已迁到 `app_backend/infrastructure/browser_runtime/`。文中提到的 `SeleniumLoginAdapter` 现名为 `BrowserLoginAdapter`；`selenium_login_runner.py` 已移除，当前等价主链收口在 `login_adapter.py` 内的 `ManagedEdgeCdpLoginRunner`。

**Historical Branch Note:** 文中提到的 `managed_profile_seed.py` / seed profile / Tampermonkey 预装方案最终没有进入当前活跃实现，现应视为废案记录，不再作为现状说明。

---

## File Structure

- Create: `app_backend/infrastructure/session_bundle/models.py`
  负责 bundle 生命周期、schema version、metadata/value object，避免把 staged/verified/active 状态散落在任务代码里。
- Create: `app_backend/infrastructure/session_bundle/protection.py`
  负责 Windows 本地凭据保护封装与序列化/反序列化入口，默认用当前用户上下文做 encryption-at-rest。
- Create: `app_backend/infrastructure/repositories/account_session_bundle_repository.py`
  负责 SQLite 元数据 + 加密 payload 文件的原子写入、激活、删除、读取与清理。
- Create: `app_backend/infrastructure/selenium/login_execution_result.py`
  负责内部 `LoginExecutionResult` / `CapturedLoginIdentity` / `StagedBundleRef`，让 `LoginCapture` 退化为兼容字段。
- Create: `app_backend/infrastructure/selenium/managed_browser_runtime.py`
  负责受管 runtime 路径解析、应用私有目录布局、runtime 可执行文件定位与 app-private 根目录读取。
- Create: `app_backend/infrastructure/selenium/managed_profile_seed.py`
  负责 seed profile 版本化、初始化、克隆与禁止回写 seed 的边界。
- Create: `app_backend/infrastructure/selenium/login_refresh_verifier.py`
  负责刷新 `/user/user/` 后的网络/页面双探针验真，避免继续扩大 `selenium_login_runner.py`。
- Modify: `app_backend/infrastructure/selenium/selenium_login_runner.py`
  接入 managed runtime/seed clone、刷新验真、会话资产采集并返回 `LoginExecutionResult` 所需 payload。
- Modify: `app_backend/infrastructure/selenium/login_adapter.py`
  保持外部 `run_login(proxy_url=..., emit_state=...)` 调用方式不变，但内部返回 `LoginExecutionResult`，并保留 `LoginCapture` 兼容访问。
- Modify: `app_backend/workers/tasks/login_task.py`
  负责 staged bundle 保存、同账号激活、冲突时写入 pending conflict 中的 bundle 引用。
- Modify: `app_backend/application/use_cases/resolve_login_conflict.py`
  负责 `verified -> active` 归属、`cancel` 丢弃 bundle、`replace_with_new_account` 时原子迁移 bundle。
- Modify: `app_backend/application/use_cases/delete_account.py`
  负责删除账号时连带删除其 active bundle。
- Modify: `app_backend/infrastructure/db/models.py`
  新增 bundle metadata 表模型。
- Modify: `app_backend/infrastructure/db/base.py`
  创建/迁移 bundle metadata 表。
- Modify: `app_backend/main.py`
  负责 wiring bundle repository 和登录链依赖。
- Modify: `app_desktop_web/python_backend.js`
  向 Python backend 传入应用私有目录环境变量，用作 runtime/seed/bundle 根目录。
- Modify: `tests/backend/test_login_adapter_contract.py`
  锁定 `LoginCapture` 兼容语义和内部 `LoginExecutionResult` 映射。
- Modify: `tests/backend/test_login_task_flow.py`
  锁定同账号登录后的 bundle 激活与刷新验真成功流。
- Modify: `tests/backend/test_login_conflict_flow.py`
  锁定冲突任务只暂存 bundle、不提前绑定账号。
- Modify: `tests/backend/test_account_routes.py`
  锁定删除账号时同步删除 bundle。
- Modify: `tests/backend/test_backend_main_entry.py`
  锁定 `create_app()` wiring 新仓储和依赖。
- Modify: `tests/backend/test_selenium_login_runner.py`
  锁定 managed runtime/seed clone/refresh probe 的 runner 行为。
- Create: `tests/backend/test_account_session_bundle_repository.py`
  覆盖 staged/verified/active 生命周期、atomic replace、single-writer 和清理。
- Create: `tests/backend/test_login_refresh_verifier.py`
  覆盖刷新成功、刷新回登录页、用户不一致、关键 cookie 丢失。
- Create: `app_desktop_web/tests/electron/python_backend.test.js`
  复用现有文件，新增应用私有目录环境变量透传断言。

## Chunk 1: Managed Browser Login Foundation

### Task 1: 先写 bundle 仓储与 schema 的失败测试

**Files:**
- Create: `tests/backend/test_account_session_bundle_repository.py`
- Modify: `tests/backend/test_account_routes.py`
- Modify: `tests/backend/test_backend_main_entry.py`

- [ ] **Step 1: 写失败测试，锁定 bundle 元数据与生命周期**
  覆盖：
  - `staged -> verified -> active -> superseded -> deleted`
  - 同账号第二次激活时旧 bundle 进入 `superseded`
  - 读接口只返回 `active`
  - 删除账号会连带删除 active bundle

- [ ] **Step 2: 运行聚焦 pytest，确认因为 bundle 仓储未实现而失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_session_bundle_repository.py tests/backend/test_account_routes.py tests/backend/test_backend_main_entry.py -q`
Expected: FAIL，提示缺少 bundle repository / metadata wiring / delete cleanup。

- [ ] **Step 3: 最小实现 SQLite metadata + 加密 payload 文件仓储**
  创建：
  - `app_backend/infrastructure/session_bundle/models.py`
  - `app_backend/infrastructure/session_bundle/protection.py`
  - `app_backend/infrastructure/repositories/account_session_bundle_repository.py`
  修改：
  - `app_backend/infrastructure/db/models.py`
  - `app_backend/infrastructure/db/base.py`
  - `app_backend/main.py`
  - `app_backend/application/use_cases/delete_account.py`

- [ ] **Step 4: 复跑聚焦 pytest，确认 bundle 仓储与删除清理转绿**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_session_bundle_repository.py tests/backend/test_account_routes.py tests/backend/test_backend_main_entry.py -q`
Expected: PASS

- [ ] **Step 5: 提交该组 foundation 变更**

Run: `git add app_backend/infrastructure/session_bundle app_backend/infrastructure/repositories/account_session_bundle_repository.py app_backend/infrastructure/db/models.py app_backend/infrastructure/db/base.py app_backend/main.py app_backend/application/use_cases/delete_account.py tests/backend/test_account_session_bundle_repository.py tests/backend/test_account_routes.py tests/backend/test_backend_main_entry.py && git commit -m "feat: add account session bundle repository"`

### Task 2: 先写 Node/Python 私有目录透传测试，再接入受管 runtime 根目录

**Files:**
- Modify: `app_desktop_web/python_backend.js`
- Modify: `app_desktop_web/tests/electron/python_backend.test.js`
- Create: `app_backend/infrastructure/selenium/managed_browser_runtime.py`

- [ ] **Step 1: 写失败测试，锁定 Python backend 启动时会带应用私有目录环境变量**
  断言 `startPythonBackend()` 传给 child process 的 env 至少包含一个 app-private 根目录键，例如 `C5_APP_PRIVATE_DIR`。

- [ ] **Step 2: 运行聚焦 vitest，确认因为 env 未透传而失败**

Run: `npm --prefix app_desktop_web test -- --run tests/electron/python_backend.test.js`
Expected: FAIL，提示 spawn 参数缺少 app-private env。

- [ ] **Step 3: 最小实现 env 透传与 runtime 根目录解析**
  修改：
  - `app_desktop_web/python_backend.js`
  创建：
  - `app_backend/infrastructure/selenium/managed_browser_runtime.py`
  先只做：
  - app-private 根目录解析
  - runtime/seed/bundle 子目录布局
  - 受管 runtime 路径选择 contract

- [ ] **Step 4: 复跑聚焦 vitest 与后端聚焦 pytest**

Run: `npm --prefix app_desktop_web test -- --run tests/electron/python_backend.test.js`
Expected: PASS

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_backend_main_entry.py -q`
Expected: PASS

- [ ] **Step 5: 提交 launcher/runtime 变更**

Run: `git add app_desktop_web/python_backend.js app_desktop_web/tests/electron/python_backend.test.js app_backend/infrastructure/selenium/managed_browser_runtime.py tests/backend/test_backend_main_entry.py && git commit -m "feat: wire managed browser runtime root"`

### Task 3: 先写刷新验真与受管 seed session 的失败测试

**Files:**
- Create: `tests/backend/test_login_refresh_verifier.py`
- Modify: `tests/backend/test_selenium_login_runner.py`
- Create: `app_backend/infrastructure/selenium/managed_profile_seed.py`
- Create: `app_backend/infrastructure/selenium/login_refresh_verifier.py`
- Modify: `app_backend/infrastructure/selenium/selenium_login_runner.py`

- [ ] **Step 1: 写失败测试，锁定刷新验真与 managed seed clone 行为**
  覆盖：
  - 登录成功后必须刷新一次 `/user/user/`
  - `/api/v1/user/v2/userInfo` 命中同一 `userId` 才算成功
  - 页面探针作为网络探针缺失时的兜底
  - `NC5_deviceId` 或 token cookie 刷新后丢失即失败
  - 每次登录都从 seed clone 出新的临时 session，不复用上一个用户现场

- [ ] **Step 2: 运行聚焦 pytest，确认因为 verifier/seed clone 未实现而失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_refresh_verifier.py tests/backend/test_selenium_login_runner.py -q`
Expected: FAIL，提示缺少 refresh verifier、managed seed clone 或成功判定不符。

- [ ] **Step 3: 最小实现 verifier、seed clone 与 runner 集成**
  创建：
  - `app_backend/infrastructure/selenium/managed_profile_seed.py`
  - `app_backend/infrastructure/selenium/login_refresh_verifier.py`
  修改：
  - `app_backend/infrastructure/selenium/selenium_login_runner.py`
  要求：
  - runner 登录完成后主动刷新
  - 验真失败不返回成功 payload
  - 直连/代理都走统一 managed session 启动入口

- [ ] **Step 4: 复跑聚焦 pytest，让 runner 与 refresh verifier 转绿**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_refresh_verifier.py tests/backend/test_selenium_login_runner.py -q`
Expected: PASS

- [ ] **Step 5: 提交 refresh verification 变更**

Run: `git add app_backend/infrastructure/selenium/managed_profile_seed.py app_backend/infrastructure/selenium/login_refresh_verifier.py app_backend/infrastructure/selenium/selenium_login_runner.py tests/backend/test_login_refresh_verifier.py tests/backend/test_selenium_login_runner.py && git commit -m "feat: verify login session after refresh"`

### Task 4: 先写 adapter/task/conflict 的失败测试，再引入 `LoginExecutionResult`

**Files:**
- Create: `app_backend/infrastructure/selenium/login_execution_result.py`
- Modify: `app_backend/infrastructure/selenium/login_adapter.py`
- Modify: `app_backend/workers/tasks/login_task.py`
- Modify: `app_backend/application/use_cases/resolve_login_conflict.py`
- Modify: `tests/backend/test_login_adapter_contract.py`
- Modify: `tests/backend/test_login_task_flow.py`
- Modify: `tests/backend/test_login_conflict_flow.py`

- [ ] **Step 1: 写失败测试，锁定内部结果对象与 bundle staging/activation**
  覆盖：
  - adapter 仍可返回 `LoginCapture` 兼容字段
  - 登录成功时先保存 `staged/verified bundle` 再激活
  - 同账号登录直接激活到当前账号
  - 冲突登录时 pending conflict payload 只暴露 bundle 引用，不直接把 bundle 绑到当前账号
  - `cancel` 会清理 `staged/verified bundle`

- [ ] **Step 2: 运行聚焦 pytest，确认因为 `LoginExecutionResult` 和冲突 staging 规则缺失而失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`
Expected: FAIL，提示返回值、pending conflict payload 或 bundle 激活逻辑不符。

- [ ] **Step 3: 最小实现内部结果对象与任务/冲突流**
  创建：
  - `app_backend/infrastructure/selenium/login_execution_result.py`
  修改：
  - `app_backend/infrastructure/selenium/login_adapter.py`
  - `app_backend/workers/tasks/login_task.py`
  - `app_backend/application/use_cases/resolve_login_conflict.py`
  要求：
  - 外部 API、任务状态名、前端交互不变
  - 内部改为 `LoginExecutionResult`
  - 只有归属决策完成后才把 bundle 提升为 `active`

- [ ] **Step 4: 复跑聚焦 pytest，让 adapter/task/conflict 转绿**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交登录任务流变更**

Run: `git add app_backend/infrastructure/selenium/login_execution_result.py app_backend/infrastructure/selenium/login_adapter.py app_backend/workers/tasks/login_task.py app_backend/application/use_cases/resolve_login_conflict.py tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py && git commit -m "feat: stage and activate account session bundles"`

### Task 5: 补兼容回归，锁定旧账号 fallback 与删除/覆盖闭环

**Files:**
- Modify: `tests/backend/test_account_repository.py`
- Modify: `tests/backend/test_account_routes.py`
- Modify: `tests/backend/test_login_conflict_flow.py`
- Modify: `app_backend/infrastructure/repositories/account_repository.py`
- Modify: `app_backend/application/use_cases/delete_account.py`

- [ ] **Step 1: 写失败测试，锁定 bundle 缺失时仍回退旧字段、替换账号时清理旧 bundle**
  覆盖：
  - 老账号只有 `cookie_raw` 也能继续运行
  - bundle 不兼容时浏览器恢复态禁用，但旧字段不立即失效
  - `replace_with_new_account` 后旧账号 bundle 被清理，新账号拿到新的 active bundle

- [ ] **Step 2: 运行聚焦 pytest，确认因为 fallback / cleanup 规则未收口而失败**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_repository.py tests/backend/test_account_routes.py tests/backend/test_login_conflict_flow.py -q`
Expected: FAIL

- [ ] **Step 3: 最小实现 fallback 与 cleanup 规则**
  修改：
  - `app_backend/infrastructure/repositories/account_repository.py`
  - `app_backend/application/use_cases/delete_account.py`
  - 如需要，再最小补充 bundle repository 的读取辅助方法

- [ ] **Step 4: 复跑聚焦 pytest，让兼容/删除闭环转绿**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_repository.py tests/backend/test_account_routes.py tests/backend/test_login_conflict_flow.py -q`
Expected: PASS

- [ ] **Step 5: 提交兼容与清理变更**

Run: `git add app_backend/infrastructure/repositories/account_repository.py app_backend/application/use_cases/delete_account.py tests/backend/test_account_repository.py tests/backend/test_account_routes.py tests/backend/test_login_conflict_flow.py && git commit -m "feat: preserve legacy account fallback with bundle cleanup"`

### Task 6: 聚焦验收与收口

**Files:**
- Test: `tests/backend/test_account_session_bundle_repository.py`
- Test: `tests/backend/test_login_refresh_verifier.py`
- Test: `tests/backend/test_selenium_login_runner.py`
- Test: `tests/backend/test_login_adapter_contract.py`
- Test: `tests/backend/test_login_task_flow.py`
- Test: `tests/backend/test_login_conflict_flow.py`
- Test: `tests/backend/test_account_routes.py`
- Test: `tests/backend/test_backend_main_entry.py`
- Test: `app_desktop_web/tests/electron/python_backend.test.js`
- Modify: `README.md`

- [ ] **Step 1: 更新 README，写清第一版受管登录与 bundle 语义**
  说明：
  - 登录成功标准 = 刷新验真成功
  - 账号删除会同步删除 bundle
  - 老账号无 bundle 时仍走旧字段 fallback

- [ ] **Step 2: 运行后端聚焦 pytest**

Run: `.\.venv\Scripts\python.exe -m pytest tests/backend/test_account_session_bundle_repository.py tests/backend/test_login_refresh_verifier.py tests/backend/test_selenium_login_runner.py tests/backend/test_login_adapter_contract.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py tests/backend/test_account_routes.py tests/backend/test_backend_main_entry.py -q`
Expected: PASS

- [ ] **Step 3: 运行桌面端聚焦 vitest**

Run: `npm --prefix app_desktop_web test -- --run tests/electron/python_backend.test.js`
Expected: PASS

- [ ] **Step 4: 检查 diff 范围并做最终提交**

Run: `git diff --stat`
Expected: 只包含 managed browser runtime / bundle / login flow / README 相关改动。

- [ ] **Step 5: 提交最终收口变更**

Run: `git add README.md app_backend app_desktop_web/tests/electron/python_backend.test.js app_desktop_web/python_backend.js tests/backend && git commit -m "feat: add managed browser account session foundation"`
