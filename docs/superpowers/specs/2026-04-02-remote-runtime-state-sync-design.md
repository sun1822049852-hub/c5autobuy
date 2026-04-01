# 远端运行时状态同步改造设计

日期：2026-04-02

## 1. 目标

为当前桌面 Web 前端建立统一的远端运行时状态链路，使 `query-system` 与 `purchase-system` 在远端模式下遵循同一套数据原则：

- 启动时仅做一次 `/app/bootstrap`
- 运行中主状态仅通过 `/ws/runtime` 持续推送更新
- 页面切换不再触发主状态补拉与轮询
- 断线时保留最后一次有效状态，只更新连接状态

本次设计明确不覆盖以下目标：

- renderer reload 后的本地快照恢复
- 前端进程重建后的状态续接
- 诊断侧栏的实时化改造

## 2. 当前问题

当前前端已经有 `app_runtime_store`、`runtime_connection_manager` 和 keep-alive 页面壳，但数据链路仍然分裂：

1. `App` 在 remote 模式下只调用一次 `/app/bootstrap`，并未真正连接 `/ws/runtime`。
2. `query-system` 与 `purchase-system` 页面各自维护主数据加载逻辑。
3. `purchase-system` 页面在激活时仍会补拉运行态，并维持 1.5 秒 polling。
4. `purchase-system` 在真实数据未就绪时会落回 preview fallback，造成“像默认页”的观感。
5. `query-system` 与 `purchase-system` 中仍有一部分跨切页应保留的状态散落在页面本地 `useState` 中。

因此现在出现的现象不是单点 bug，而是架构上的双轨问题：

- 一条轨道是全局 runtime store
- 另一条轨道是页面级 fetch / polling / fallback

## 3. 已确认的用户决策

以下内容已经确认：

- 最终部署形态为：前端打包成桌面 app，后端运行在主服务器。
- 采用“薄前端壳”思路，前端以展示与命令提交为主。
- 采用方案 B：
  - 全局内存态 runtime store
  - `/ws/runtime` 持续推送
  - HTTP 只做 bootstrap / resync / 显式命令
- 本次不做 renderer reload 后的本地持久化恢复。

## 4. 方案比较

### 方案 A：最小修补

- 保留现有页面级 fetch / polling
- 只把明显会闪的状态搬进全局 store

优点：

- 改动小
- 风险低

缺点：

- 数据真源仍然分裂
- 切页补拉与状态漂移仍会长期存在

### 方案 B：全局运行时事件流

- `/app/bootstrap` 负责首次全量快照
- `/ws/runtime` 负责后续主状态更新
- 页面只读全局 store

优点：

- 状态真源单一
- 最适合“桌面壳 + 远端主服务器”形态
- 切页、断线、恢复行为最容易解释和验证

缺点：

- 需要重构前端主数据生命周期

### 方案 C：完整实体缓存与本地持久化

- 在方案 B 基础上继续做本地快照、实体级缓存、版本恢复

优点：

- 上限最高

缺点：

- 超出本轮目标
- 成本与风险显著高于当前需要

### 结论

采用方案 B。

## 5. 真实后端事件边界

当前 `/ws/runtime` 已经具备可用事件流，前端应围绕真实事件设计，而不是自造协议。

当前主事件类型为：

- `query_runtime.updated`
- `purchase_runtime.updated`
- `query_configs.updated`
- `purchase_ui_preferences.updated`
- `runtime_settings.updated`
- `runtime.resync_required`

其中：

- `query_runtime.updated` 负载为完整查询运行态快照
- `purchase_runtime.updated` 负载为完整购买运行态快照
- `query_configs.updated` 负载为完整配置列表，且每个配置包含 `items` 与 `mode_settings`
- `purchase_ui_preferences.updated` 负载为购买页 UI preference 快照
- `runtime_settings.updated` 负载为购买运行时设置快照
- `runtime.resync_required` 表示事件历史不足，前端必须强制重拉 `/app/bootstrap`

这意味着前端可以把“运行态”和“配置集”都纳入事件驱动主链路。

## 6. 总体架构

### 6.1 启动链路

remote 模式下前端启动流程固定为：

1. 创建 `client`
2. 创建 `app_runtime_store`
3. 调用一次 `/app/bootstrap`
4. 用 bootstrap 快照 hydrate store
5. 读取 bootstrap `version`
6. 建立 `/ws/runtime?since_version=<version>` 长连接
7. 后续所有主状态由 runtime event 驱动

### 6.2 断线与恢复链路

WebSocket 断开后：

1. 不清空现有业务状态
2. `connection.state` 置为 `stale` 或 `error`
3. 保留最后一次有效快照继续展示
4. 调度强制 `/app/bootstrap`
5. bootstrap 成功后刷新 `lastEventVersion`
6. 重新建立 `/ws/runtime`

### 6.3 页面职责

页面层不再拥有主状态生命周期。

页面职责收口为：

- 从 store 读取展示数据
- 维护少量纯 UI 瞬时态
- 发起显式 HTTP 命令
- 等待后端事件回流更新最终状态

## 7. Store 结构设计

`app_runtime_store` 调整为以下结构：

### 7.1 bootstrap

- `state`
- `hydratedAt`
- `version`

### 7.2 connection

- `state`
- `stale`
- `lastSyncAt`
- `lastEventVersion`
- `lastError`

### 7.3 querySystem

- `configsById`
- `configOrder`
- `capacitySummary`
- `runtimeStatus`
- `ui.selectedConfigId`
- `draft.currentConfig`
- `draft.hasUnsavedChanges`

说明：

- `query_configs.updated` 已经可承接完整配置详情，因此 `querySystem` 不再需要依赖“切页再补一次 `getQueryConfig`”作为常规路径。

### 7.4 purchaseSystem

- `runtimeStatus`
- `uiPreferences`
- `runtimeSettings`
- `ui.selectedConfigId`
- `draft.manualAllocationDrafts`
- `draft.purchaseSettingsDraft`
- `draft.querySettingsDraft`

说明：

- 购买页中会跨切页保留、且与业务状态强相关的草稿态，进入全局 store。
- 购买页纯 UI 开关与弹层位置继续保留本地。

## 8. 事件映射规则

前端需要一层统一的 event reducer。

映射规则固定如下：

- `bootstrap`
  - hydrate `bootstrap`
  - hydrate `querySystem` server-owned slices
  - hydrate `purchaseSystem` server-owned slices
- `query_configs.updated`
  - 整包替换 `querySystem.configsById` 与 `configOrder`
- `query_runtime.updated`
  - 整包替换 `querySystem.runtimeStatus`
- `purchase_runtime.updated`
  - 整包替换 `purchaseSystem.runtimeStatus`
- `purchase_ui_preferences.updated`
  - 整包替换 `purchaseSystem.uiPreferences`
- `runtime_settings.updated`
  - 整包替换 `purchaseSystem.runtimeSettings`
- `runtime.resync_required`
  - 不清空业务数据
  - 仅标记连接过期
  - 立即强制执行一次 `/app/bootstrap`

runtime event 不得覆盖以下 slice：

- `querySystem.ui`
- `querySystem.draft`
- `purchaseSystem.ui`
- `purchaseSystem.draft`

## 9. 页面收口方案

### 9.1 App 层

`App.jsx` 收口为：

- 初始化 runtime store
- 初始化 connection manager
- remote 模式下执行 `bootstrap + connectRuntimeStream`
- 保持 keep-alive 页面挂载

`App` 不再参与 query / purchase 页面级主数据补拉。

### 9.2 Query 页面

`use_query_system_page.js` 改造目标：

- 删除激活时的主数据 bootstrap 三连拉取
- 删除常规路径下的 detail 补拉依赖
- 主数据全部来自 store
- 仅保留用户显式命令：
  - 保存配置
  - 新增 / 编辑 / 删除 item
  - 显式刷新 detail

命令成功后不手工拼主状态，而是等待：

- `query_configs.updated`
- `query_runtime.updated`

### 9.3 Purchase 页面

`use_purchase_system_page.js` 改造目标：

- 删除激活时的主数据补拉
- 删除 1.5 秒 polling
- 删除 `PREVIEW_ITEM_ROWS` 主兜底
- 主运行态、配置相关状态、草稿相关状态从 store 读取
- 页面本地仅保留：
  - 弹窗开关
  - 过程型 pending 状态
  - 浮层位置和尺寸

## 10. 非目标

本轮设计明确不做：

- renderer reload 后恢复上次状态
- 本地落盘 runtime 快照
- 诊断面板实时推送化
- 将所有 UI 小状态都搬入全局 store

## 11. 实施顺序

按以下顺序落地，禁止穿插大范围同时修改：

1. 接通 `/ws/runtime` 客户端
2. 扩展 `runtime_connection_manager`
3. 扩展 `app_runtime_store` 与 event reducer
4. 收掉 query 页主数据 fetch
5. 收掉 purchase 页主数据 fetch 与 polling
6. 删除 preview fallback 与冗余 hydration 路径
7. 清理旧测试并补齐新测试

## 12. 测试策略

至少补齐以下验证：

### 12.1 connection manager

- bootstrap 后建立 runtime stream
- 接收 `query_runtime.updated` 会更新 store
- 接收 `purchase_runtime.updated` 会更新 store
- 接收 `runtime.resync_required` 会强制 bootstrap
- socket 断开后业务数据保留，连接态变 stale

### 12.2 runtime store

- runtime event 映射正确
- `query_configs.updated` 可覆盖完整配置树
- event 不覆盖 UI / draft slice
- resync 只更新连接状态与 bootstrap，不回退到空视图

### 12.3 页面行为

- 切换 query 页不再重新拉主数据
- 切换 purchase 页不再重新拉主数据
- purchase 页不再依赖 preview fallback 作为主展示
- 断线后保留最后有效数据
- 恢复后通过 resync 或后续 event 追平

## 13. 验收标准

本轮完成标准为：

1. remote 模式下 `App` 启动后会建立 `/ws/runtime`
2. query / purchase 页面切换时不再出现主内容回默认态
3. purchase 页不再依赖 preview fallback 伪装数据
4. 断线时页面保留最后一次有效业务态
5. 恢复连接后状态可以自动 resync
6. 页面主状态真源可以明确解释为：
   - 首次 `/app/bootstrap`
   - 运行时 `/ws/runtime`
   - 用户命令 HTTP

## 14. 风险与控制

主要风险：

1. 旧代码仍保留页面级 fetch，导致双轨并存。
2. `query_configs.updated` 进入前端后 shape 统一不彻底。
3. purchase 页草稿迁移边界不清，导致 store 过重或状态遗漏。

控制策略：

- 分阶段修改
- 每阶段先补测试再删旧路径
- 明确区分业务状态与纯 UI 瞬时态

## 15. 结论

本次改造不是单纯修复“页面掉状态”，而是把前端改成真正适合远端后端架构的 thin-client 运行时模型。

完成后，前端状态行为将更稳定、可解释、可验证，也更适合后续桌面 app 打包与远端主服务器部署。
