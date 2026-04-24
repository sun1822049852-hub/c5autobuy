# 浏览器查询开通放权设计

日期：2026-04-24

## 目标

把账号中心里“浏览器查询”开关的“打开”动作纳入程序会员放权控制；未获放权时，前端必须弹窗提示“当前此功能未开放”。

## 边界

- 只控制“打开浏览器查询”这一个动作。
- 不影响关闭浏览器查询。
- 不改登录成功、首次绑定默认关闭浏览器查询、白名单 / OpenAPI、购买配置、查询主链与只读锁主语义。
- 不把账号中心其它编辑动作一起升级成细粒度放权。

## 现状

- 浏览器查询开关前端入口在账号中心“浏览器查询”列按钮。
- 打开时前端发送 `PATCH /accounts/{id}/query-modes`，请求体是 `{ browser_query_enabled: true }`。
- 后端当前只把该请求落成 `token_enabled=True`，没有单独的程序会员细粒度 guard。
- 现有程序会员 guard 主要覆盖只读锁定态与 `runtime.start`，错误通过 `ProgramAccessProvider` 统一解析。

## 方案

### 后端

- 为“打开浏览器查询”增加独立 guard action：`account.browser_query.enable`。
- `PATCH /accounts/{id}/query-modes` 仅当请求要把浏览器查询从关改开时，才执行这条 guard。
- guard 未通过时，返回：
  - `code = "program_feature_not_enabled"`
  - `message = "当前此功能未开放"`
  - `action = "account.browser_query.enable"`
- `LocalPassThroughGateway` 继续放行，不影响源码本地放行模式。
- `CachedProgramAccessGateway` 与 `RemoteEntitlementGateway` 在总开关 `program_access_enabled` 之外，再要求快照显式授予浏览器查询开通权限；未显式授予时默认拒绝。

### 放权键

- guard action：`account.browser_query.enable`
- 远端权限兼容口径：
  - `permissions` 可包含 `account.browser_query.enable`
  - `feature_flags` 可包含 `account_browser_query_enable = true`

说明：未显式授予即视为未开放。

### 前端

- 账号中心“浏览器查询”按钮保持可点，不提前灰掉。
- 用户点击“打开”时，仍走原 PATCH 流程。
- 如果后端返回 `program_feature_not_enabled + action=account.browser_query.enable`，账号中心就地弹出一个小弹窗，正文固定为“当前此功能未开放”。
- 其它错误仍沿用现有错误日志与 Program Access 共享错误出口，不扩散到新的弹窗分支。

## 风险控制

- 只在“关 -> 开”时加 guard，避免误伤“开 -> 关”。
- 细粒度放权默认关闭，只有远端明确授权才可开启，避免绕过会员限制。
- 前端弹窗只绑定这条 action，避免把别的程序会员错误都误显示成“功能未开放”。

## 验证

- 后端路由测试：未放权时开启浏览器查询返回 403 + 指定 code/message/action；关闭浏览器查询仍可通过。
- 后端 gateway 测试：缺少 `account.browser_query.enable` 时 deny，存在该权限时 allow。
- 前端编辑测试：点击开启浏览器查询时不再发成功 PATCH 落地，而是出现“当前此功能未开放”弹窗。
- 前端回归：关闭浏览器查询的原有 payload 不变。
