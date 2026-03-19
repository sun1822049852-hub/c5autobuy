# Login Proxy Dialog Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在账号中心点击“发起登录”时先弹出代理设置框，允许用户确认或修改代理后再启动登录。

**Architecture:** 前端窗口层负责拉起登录代理弹窗，弹窗只产出代理配置 payload；控制器负责编排“取消直接返回”“代理未变化直接登录”“代理变化先更新账号再登录”三条路径。后端登录接口和登录任务保持不变，仍从账号持久化状态读取代理。

**Tech Stack:** Python, PySide6, pytest

---

## 文件结构

- Modify: `app_frontend/app/dialogs/create_account_dialog.py`
- Create: `app_frontend/app/dialogs/login_proxy_dialog.py`
- Modify: `app_frontend/app/controllers/account_center_controller.py`
- Modify: `app_frontend/app/windows/account_center_window.py`
- Modify: `tests/frontend/test_account_dialogs.py`
- Modify: `tests/frontend/test_account_center_controller.py`

注：按仓库规则，本计划不包含 git 提交、分支或 worktree 操作。

## Task 1: 先写登录代理弹窗与控制器失败测试

- [ ] 为 `tests/frontend/test_account_dialogs.py` 增加 `LoginProxyDialog` 预填与 payload 组装测试
- [ ] 为 `tests/frontend/test_account_center_controller.py` 增加“代理变化时先更新再登录”的测试
- [ ] 为 `tests/frontend/test_account_center_controller.py` 增加“代理未变化时直接登录”的测试
- [ ] 为 `tests/frontend/test_account_center_controller.py` 增加“取消时不更新也不登录”的测试
- [ ] 运行定向测试，确认因缺少弹窗和编排逻辑而失败

Run:

```powershell
pytest "tests/frontend/test_account_dialogs.py" "tests/frontend/test_account_center_controller.py" -q
```

Expected:

- 新增测试失败
- 失败原因分别指向缺少 `LoginProxyDialog` 或缺少新的控制器路径

## Task 2: 最小实现登录代理弹窗

- [ ] 在 `create_account_dialog.py` 中提取可复用的代理字段初始化、预填和 payload 组装辅助能力
- [ ] 新建 `login_proxy_dialog.py`，只保留代理相关 UI，不暴露备注名、API Key、查询开关
- [ ] 让 `LoginProxyDialog` 支持根据当前账号 `proxy_mode` / `proxy_url` 预填
- [ ] 复跑对话框定向测试，确认弹窗测试转绿

Run:

```powershell
pytest "tests/frontend/test_account_dialogs.py" -q
```

Expected:

- `LoginProxyDialog` 相关测试通过
- 现有账号对话框测试继续通过

## Task 3: 最小实现登录前代理编排逻辑

- [ ] 在 `AccountCenterController` 增加接收登录代理 payload 的入口
- [ ] 比较当前账号代理与弹窗提交代理，区分“先更新再登录”和“直接登录”
- [ ] 保持现有登录任务启动、任务流监听和冲突处理逻辑不变
- [ ] 在 `AccountCenterWindow` 中把“发起登录”改为先弹窗，再把结果交给 controller
- [ ] 复跑控制器定向测试，确认三条路径全部通过

Run:

```powershell
pytest "tests/frontend/test_account_center_controller.py" -q
```

Expected:

- 新增控制器测试通过
- 现有登录冲突流测试继续通过

## Task 4: 完整验证

- [ ] 运行登录相关前端测试集
- [ ] 按结果检查是否有窗口层回归
- [ ] 汇总通过项与剩余风险

Run:

```powershell
pytest "tests/frontend/test_account_dialogs.py" "tests/frontend/test_account_center_controller.py" "tests/frontend/test_account_detail_panel.py" "tests/frontend/test_account_center_window_status.py" -q
```

Expected:

- 目标测试通过
- 无新增失败
