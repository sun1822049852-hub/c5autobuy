# Packaged Python Runtime Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Windows packaged release 从“内置完整开发 `.venv`”改成“首启下载 Python 官方 embeddable runtime + 使用打包内最小 Python 依赖资源启动 backend”，在保持开发态 `.venv` 流程不变的前提下显著缩小发行包体积。

**Architecture:** 打包前先从当前开发 `.venv` 导出一个经过裁剪的 `python_deps` 资源目录，只保留 backend 运行所需 site-packages，不再把整套 `.venv` 带进发行包。packaged release 启动时由新的 runtime bootstrap 层检查应用私有目录中的托管 Python runtime；若缺失或损坏，则从 Python 官方下载固定版本 embeddable zip、做 SHA256 校验、解压到 staging、安装最小依赖并写入 manifest，成功后再把 `python.exe` 交给现有 backend 启动链。

**Tech Stack:** Electron main process (CommonJS) + ESM helper modules；Node.js `fs/path/https/crypto/stream`；Vitest；Python 3.11 Windows embeddable package；现有 FastAPI backend

---

## File Map

- Create: `app_desktop_web/python_runtime_config.cjs`
  负责固定官方 embeddable runtime 版本、下载 URL、SHA256、托管目录命名、依赖裁剪排除名单。
- Create: `app_desktop_web/python_runtime_resources.cjs`
  负责打包前从开发 `.venv` 导出最小 `build/python_deps` 资源，并提供构建阶段可复用的路径/校验辅助。
- Create: `app_desktop_web/python_runtime_bootstrap.js`
  负责 packaged release 下的 runtime 复用、下载、校验、staging 解压、`python_deps` 安装、`._pth` 修补与 manifest 写入。
- Modify: `app_desktop_web/electron-builder.config.cjs`
  移除 `.venv` extraResources，改为打包 `build/python_deps`。
- Modify: `app_desktop_web/electron-builder-preflight.cjs`
  打包前先导出最小 Python 依赖资源，并把 preflight 校验从“整包 `.venv` 可 import”改成“开发 Python + 导出资源可支持 packaged runtime 方案”。
- Modify: `app_desktop_web/electron-main.cjs`
  packaged release 启动时先 `ensureManagedPythonRuntime()`，成功后再 `startPythonBackend()`；开发态继续走 `resolvePythonExecutable()`。
- Modify: `app_desktop_web/python_backend.js`
  收口为“开发态 Python 解析 + 启动 backend”的职责，不再假定 packaged release 一定来自 `resources/.venv`。
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
  锁定 builder config、preflight 与 packaged startup 新契约。
- Modify: `app_desktop_web/tests/electron/python_backend.test.js`
  锁定开发态 `.venv` 解析不回退。
- Create: `app_desktop_web/tests/electron/python_runtime_bootstrap.test.js`
  锁定 runtime 复用、下载、校验、解压、依赖安装、失败清理与 manifest 行为。
- Modify: `docs/agent/session-log.md`
  记录实现结果、打包体积变化与验证证据。
- Modify: `docs/agent/memory.md`（仅在形成新的稳定规则时）
  若需要，沉淀新的发行稳定约束。
- Modify: `README.md`（若实现改变了打包/首次启动说明）
  同步正式使用说明。

## Chunk 1: Lock The New Packaged Runtime Contract With Failing Tests

### Task 1: 锁定 builder config 与 preflight 不再依赖完整 `.venv`

**Files:**
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Modify: `app_desktop_web/electron-builder.config.cjs` (read-only until green step)
- Modify: `app_desktop_web/electron-builder-preflight.cjs` (read-only until green step)

- [ ] **Step 1: 写失败测试，断言 builder config 的 `extraResources` 不再包含 `.venv`，而是包含 `python_deps`**
- [ ] **Step 2: 写失败测试，断言 preflight 会准备最小 Python 依赖资源，而不是校验 `resources/.venv`**
- [ ] **Step 3: 运行 focused packaging tests，确认红灯**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`

Expected: FAIL，至少有一个断言仍看到 `.venv` 或旧 preflight 行为。

### Task 2: 锁定 packaged release 启动前必须完成 managed runtime bootstrap

**Files:**
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Modify: `app_desktop_web/electron-main.cjs` (read-only until green step)

- [ ] **Step 1: 写失败测试，断言 packaged embedded startup 会先调用 `ensureManagedPythonRuntime`，再把返回的托管 `python.exe` 传给 `startPythonBackend`**
- [ ] **Step 2: 写失败测试，断言 runtime bootstrap 失败时不会调用 backend 启动，并落到 failure window**
- [ ] **Step 3: 运行 focused packaging tests，确认红灯**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`

Expected: FAIL，packaged 启动链尚未接入新的 bootstrap。

### Task 3: 锁定 runtime bootstrap 的成功复用与失败清理行为

**Files:**
- Create: `app_desktop_web/tests/electron/python_runtime_bootstrap.test.js`
- Create: `app_desktop_web/python_runtime_bootstrap.js` (read-only until green step)

- [ ] **Step 1: 写失败测试，断言 manifest 与 `python.exe` 都完整时直接复用，不触发下载**
- [ ] **Step 2: 写失败测试，断言缺失 runtime 时会下载 zip、校验 SHA256、解压 staging、安装 `python_deps` 并写 manifest**
- [ ] **Step 3: 写失败测试，断言 SHA256 不匹配或解压失败时会清理临时文件 / staging 并抛出可展示错误**
- [ ] **Step 4: 运行 focused bootstrap tests，确认红灯**

Run: `npm --prefix app_desktop_web test -- tests/electron/python_runtime_bootstrap.test.js --run`

Expected: FAIL，模块缺失或行为未实现。

## Chunk 2: Build The Minimal Python Resource Export Path

### Task 4: 实现固定 runtime 配置与最小依赖导出脚本

**Files:**
- Create: `app_desktop_web/python_runtime_config.cjs`
- Create: `app_desktop_web/python_runtime_resources.cjs`
- Modify: `app_desktop_web/electron-builder-preflight.cjs`
- Test: `app_desktop_web/tests/electron/program_access_packaging.test.js`

- [ ] **Step 1: 写最小配置模块，固定 Python embeddable 版本、官方 URL、SHA256、托管目录名与依赖裁剪排除名单**
- [ ] **Step 2: 写最小资源导出实现，把开发 `.venv/Lib/site-packages` 裁剪复制到 `app_desktop_web/build/python_deps/Lib/site-packages`**
- [ ] **Step 3: 在 preflight 中先执行 renderer build，再导出 `python_deps`，并用开发 `.venv` 对导出结果做一次 import smoke check**
- [ ] **Step 4: 回跑 packaging tests，确认 Task 1 转绿**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`

Expected: PASS，builder config / preflight 契约转绿。

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/python_runtime_config.cjs app_desktop_web/python_runtime_resources.cjs app_desktop_web/electron-builder-preflight.cjs app_desktop_web/tests/electron/program_access_packaging.test.js
git commit -m "build: prepare packaged python runtime resources"
```

### Task 5: 把 builder config 从 `.venv` 切到 `python_deps`

**Files:**
- Modify: `app_desktop_web/electron-builder.config.cjs`
- Test: `app_desktop_web/tests/electron/program_access_packaging.test.js`

- [ ] **Step 1: 移除 `.venv` extraResources**
- [ ] **Step 2: 增加 `build/python_deps` extraResources**
- [ ] **Step 3: 保持 `app_backend`、`xsign.py`、release client config 打包路径不变**
- [ ] **Step 4: 回跑 packaging tests，确认 builder config 契约稳定**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`

Expected: PASS

## Chunk 3: Implement Packaged Runtime Bootstrap And Launch Integration

### Task 6: 实现 packaged runtime bootstrap

**Files:**
- Create: `app_desktop_web/python_runtime_bootstrap.js`
- Create: `app_desktop_web/tests/electron/python_runtime_bootstrap.test.js`

- [ ] **Step 1: 写最小路径解析与 manifest 读取逻辑**
- [ ] **Step 2: 写下载 + SHA256 校验 + staging 解压逻辑**
- [ ] **Step 3: 把 packaged `python_deps` 安装到托管 runtime 的 `Lib/site-packages`，并修补 embeddable `._pth` 以启用 site-packages**
- [ ] **Step 4: 写 manifest 完成态与损坏重试逻辑**
- [ ] **Step 5: 回跑 bootstrap tests，确认 Task 3 转绿**

Run: `npm --prefix app_desktop_web test -- tests/electron/python_runtime_bootstrap.test.js --run`

Expected: PASS

### Task 7: 接入 Electron packaged 启动链，同时保持开发态不回退

**Files:**
- Modify: `app_desktop_web/electron-main.cjs`
- Modify: `app_desktop_web/python_backend.js`
- Modify: `app_desktop_web/tests/electron/program_access_packaging.test.js`
- Modify: `app_desktop_web/tests/electron/python_backend.test.js`

- [ ] **Step 1: packaged release 启动前先调用 `ensureManagedPythonRuntime()`，只在成功后启动 backend**
- [ ] **Step 2: 开发态继续保留 `.venv` 祖先回溯解析，不引入下载链**
- [ ] **Step 3: packaged 失败路径维持 fail-closed，并沿用现有 failure window 文案通道**
- [ ] **Step 4: 回跑 packaging + python backend tests，确认 Task 2 与开发态契约转绿**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js tests/electron/python_runtime_bootstrap.test.js --run`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app_desktop_web/python_runtime_bootstrap.js app_desktop_web/electron-main.cjs app_desktop_web/python_backend.js app_desktop_web/tests/electron/program_access_packaging.test.js app_desktop_web/tests/electron/python_backend.test.js app_desktop_web/tests/electron/python_runtime_bootstrap.test.js
git commit -m "feat: bootstrap packaged python runtime"
```

## Chunk 4: Verify Packaging, Measure Size, And Update Docs

### Task 8: 跑受影响自动化验证与打包验尸

**Files:**
- Modify: `docs/agent/session-log.md`
- Modify: `docs/agent/memory.md` (only if this round creates a stable rule beyond the approved spec)
- Modify: `README.md` (if packaged startup instructions changed for users)
- Modify: `docs/superpowers/specs/2026-04-23-packaged-python-runtime-bootstrap-design.md` (only if implementation changes final design)
- Modify: `docs/superpowers/plans/2026-04-23-packaged-python-runtime-bootstrap.md`

- [ ] **Step 1: 跑 focused Electron tests**

Run: `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js tests/electron/python_runtime_bootstrap.test.js --run`

- [ ] **Step 2: 跑 `pack:win` 生成新的 `win-unpacked`**

Run: `npm --prefix app_desktop_web run pack:win`

Expected: PASS，且 `app_desktop_web/release/win-unpacked/resources/.venv` 不存在。

- [ ] **Step 3: 记录新 `win-unpacked` 与 installer 体积，和旧基线 `1.02GB / 282.77MB` 对比**

Run: `Get-ChildItem app_desktop_web/release -Force`

- [ ] **Step 4: 若环境允许，再跑 installer 构建**

Run: `npm --prefix app_desktop_web run build:win`

- [ ] **Step 5: 做 packaged smoke**

Check:
- 清空托管 Python runtime 后首次启动，确认 loading -> 下载 -> backend ready -> app
- 断网启动，确认阻断错误与重试入口

- [ ] **Step 6: 更新 session log，写清体积变化、实现范围、验证结果与剩余风险**
- [ ] **Step 7: 只有形成新的稳定规则时才更新 memory**
- [ ] **Step 8: 若用户文档受影响，同步 README 的打包 / 首启说明**
- [ ] **Step 9: 按真实执行进度勾选计划**
