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

此外，后端必须满足以下版本契约，前端实现才允许依赖 `version` 做去重与覆盖判定：

1. `/app/bootstrap` 返回的 `version` 与 `/ws/runtime` 中各 `event.version` 属于同一条全局单调递增版本序列。
2. 该版本序列由同一个 `RuntimeUpdateHub` 维护。
3. bootstrap 返回的 `version` 表示“生成该 snapshot 时 hub 的当前版本”。
4. `runtime.resync_required` 的 `version` 与普通 runtime event 处于同一版本域。
5. bootstrap snapshot 必须满足状态屏障约束：
   - 该 snapshot 至少覆盖所有 `version <= bootstrap.version` 的 server-owned 可见状态
   - 前端据此才能安全使用 `since_version=bootstrap.version` 建立后续事件流

凡是会影响 server-owned slice 的命令，后端都必须在成功后发布指定 runtime event，且该 event 必须进入同一全局版本序列。最低要求如下：

- query 配置 / item / mode setting 变更成功后，必须发布 `query_configs.updated`
- query runtime 运行态变更成功后，必须发布 `query_runtime.updated`
- purchase runtime 运行态变更成功后，必须发布 `purchase_runtime.updated`
- purchase UI preference 变更成功后，必须发布 `purchase_ui_preferences.updated`
- purchase runtime setting 变更成功后，必须发布 `runtime_settings.updated`

若某条命令成功后没有对应 event 回流，则不满足本 spec，前端也不得用 HTTP success response 直接补写主 store。

补充说明：

- `capacitySummary` 不属于本轮 runtime correctness contract 的 authoritative slice。
- 它仅作为 advisory reference slice 存在，只允许由 bootstrap / resync 更新。
- 在没有对应 runtime event 之前，任何业务写入流程都不得依赖 `capacitySummary` 作为强一致真源或保存前提。
- 任何显式刷新类 HTTP response 都不得直接写入 `capacitySummary`；若未来需要持续更新，必须新增专门 runtime event。

前端不得假设存在第二条 snapshot-only 版本线。

## 6. 总体架构

### 6.1 启动链路

remote 模式下前端启动流程固定为：

1. 创建 `client`
2. 创建 `app_runtime_store`
3. 分配首个 `connectionGeneration`
4. 在该 generation 下调用一次 `/app/bootstrap`
5. 用 bootstrap 快照 hydrate store
6. 读取 bootstrap `version`
7. 在同一 generation 下建立 `/ws/runtime?since_version=<version>` 长连接
8. 后续所有主状态由 runtime event 驱动

### 6.2 断线与恢复链路

WebSocket 断开后：

1. 不清空现有业务状态
2. `connection.state` 置为 `stale` 或 `error`
3. 保留最后一次有效快照继续展示
4. 调度强制 `/app/bootstrap`
5. bootstrap 成功后刷新 `lastEventVersion`
6. 重新建立 `/ws/runtime`

### 6.3 事件版本与连接代际规则

为避免 resync 后旧事件覆盖新状态，前端必须引入以下硬约束：

1. `since_version` 语义固定为“请求版本之后的事件”，即前端连接 `/ws/runtime?since_version=N` 时，只接受 `version > N` 的事件。
2. `connectionGeneration` 绑定一次完整的 connect attempt：
   - 分配 generation
   - 在该 generation 下执行 bootstrap
   - 在该 generation 下建立并维持 ws
3. 只有在放弃旧 connect attempt 并启动新的 reconnect / resync 周期时，才允许 bump generation。bootstrap 与其后的 ws 共享同一个 generation，二者不得各自单独 bump。
4. store reducer 只接受“当前连接代际”发出的结果；旧 socket 与旧 bootstrap 请求的迟到结果必须直接丢弃。

前端 reducer 的处理规则固定为：

- `event.version <= connection.lastEventVersion` 时丢弃
- `event.connectionGeneration !== connection.currentGeneration` 时丢弃
- bootstrap 返回结果只有在以下条件同时满足时才允许落库：
  - `response.connectionGeneration === connection.currentGeneration`
  - 普通 reconnect bootstrap 场景下：`response.version >= connection.lastEventVersion`
  - resync bootstrap 场景下：`response.version >= triggeringResyncVersion`
  - 若该 bootstrap 由 `runtime.resync_required@R` 触发，则 `response.version >= R`
- bootstrap / resync 成功落库后，将 `lastEventVersion` 直接推进到 bootstrap 返回的 `version`
- 任何晚于该版本但来自旧连接的事件，仍按代际规则丢弃

这样可以保证：

- 重复事件不回放
- 低版本事件不倒灌
- 旧连接与旧 bootstrap 请求的迟到结果不会把新状态覆盖回去

### 6.4 页面职责

页面层不再拥有主状态生命周期。

页面职责收口为：

- 从 store 读取展示数据
- 维护少量纯 UI 瞬时态
- 发起显式 HTTP 命令
- 等待后端事件回流或 resync bootstrap 更新最终状态

这里的“HTTP 命令”不是主状态真源，只是触发后端变更的命令通道。

页面本地态的硬边界如下：

- 允许：request metadata、pending flag、loading/error、toast、modal open、panel position/size
- 禁止：`optimisticConfig`、`pendingRuntimeSettings`、`temporaryRowsUntilEventArrives`、或任何与 `querySystem` / `purchaseSystem` 同 shape 的业务 shadow data 用于主渲染
- 若页面需要 optimistic feedback，只能显示请求状态文案，不能构造第二份业务对象参与主内容渲染

draft authoritative-settle 的比较契约固定如下：

- 本 spec 中所有“authoritative echo / snapshot 与当前 dirty draft 语义一致”的判定，允许由前端执行，但必须走每类 draft 唯一共享的 canonical normalizer/comparator helper。
- 禁止在不同页面、不同 hook、不同 reducer 中各自发明不同的 deep-compare / ad-hoc compare 规则。
- HTTP success 永远不能单独触发 settle clean；只有 authoritative event / resync snapshot + canonical comparator 才能触发 settle clean。
- 若未来后端提供 command correlation token / settle token，可替代 comparator；在此之前，canonical comparator 是唯一允许的前端 settle 判定机制。

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
- `capacitySummary` 当前没有独立 runtime event 来源，因此它被定义为“bootstrap / resync slice”，只在首次 `/app/bootstrap` 或强制 resync 后更新，不作为持续事件流主 slice。
- `ui.selectedConfigId` 收敛规则固定为：
  - 若当前选中配置仍存在，则保留
  - 若已不存在，则回退到 `runtimeStatus.config_id`
  - 若仍不存在，则回退到 `configOrder[0]`
  - 若配置列表为空，则回退到 `null`
- `draft.currentConfig` 增加基线元数据：
  - `baseConfigUpdatedAt`
  - `baseConfigVersion`
  - `hasRemoteChange`
  - `hasConflict`
  - `isOrphaned`

dirty draft 规则固定为：

- draft 未修改时，服务端配置更新可自动覆盖并同步
- draft 已修改时，服务端配置更新不得直接覆盖 draft
- 若服务端更新命中了当前 draft 对应配置，则默认仅更新服务端基线，并把 draft 标记为 `hasRemoteChange=true`；只有本节下文定义的 matching authoritative settle 条件满足时，才允许转为 clean
- 若服务端更新与当前 draft 编辑区域存在不可自动合并差异，则标记 `hasConflict=true`
- query config 保存命令携带 `baseConfigVersion`，HTTP success 只表示命令已被后端接受，不得直接清 `draft.hasUnsavedChanges` 或直接 patch `currentConfig`
- matching `query_configs.updated` 或等价 resync snapshot 到达时：
  - 若 authoritative config 与当前 dirty draft 语义一致，则将 `currentConfig` settle 为 clean authoritative draft，并清除 `draft.hasUnsavedChanges`、`hasRemoteChange`、`hasConflict`
  - 若 `baseConfigVersion` 已推进且 authoritative config 与当前 dirty draft 不一致，则保持 dirty，标记 `hasConflict=true`
- 保存时若 `hasConflict=true`，前端必须阻止直接提交并要求用户先处理冲突
- 若当前 draft 对应配置被远端删除，则：
  - `selectedConfigId` 按收敛规则切到新配置或 `null`
  - draft 标记为 `isOrphaned=true`、`hasConflict=true`
  - 编辑面板不得静默改绑到新配置
  - 用户只能显式丢弃 orphan draft，或通过单独“另存为新配置”流程处理

### 7.4 purchaseSystem

- `runtimeStatus`
- `uiPreferences`
- `runtimeSettings`
- `ui.selectedConfigId`
- `draft.manualAllocationDrafts`
- `draft.purchaseSettingsDraft`

说明：

- 购买页中会跨切页保留、且与业务状态强相关的草稿态，进入全局 store。
- 购买页纯 UI 开关与弹层位置继续保留本地。
- 购买页使用的“配置相关状态”不再单独复制到 `purchaseSystem`，统一直接读取 `querySystem.configsById / configOrder` 作为真源，禁止在 purchase 页再维护第二份配置树。
- `ui.selectedConfigId` 收敛规则固定为：
  - 若当前选中配置仍存在，则保留
  - 若已不存在，则回退到 `uiPreferences.selected_config_id`
  - 若仍不存在，则回退到 `runtimeStatus.active_query_config.config_id`
  - 若仍不存在，则回退到 `querySystem.configOrder[0]`
  - 若配置列表为空，则回退到 `null`
- `draft.purchaseSettingsDraft` 增加基线元数据：
  - `baseRuntimeSettingsVersion`
  - `hasRemoteChange`
  - `hasConflict`
- `purchaseSettingsDraft` 保存命令携带 `baseRuntimeSettingsVersion`，HTTP success 只表示命令已被后端接受，不得直接清 dirty / pending-save，也不得直接 patch `purchaseSettingsDraft`
- matching `runtime_settings.updated` 或等价 resync snapshot 到达时：
  - 若 authoritative runtime settings 与当前 dirty draft 语义一致，则将 `purchaseSettingsDraft` settle 为 clean authoritative draft，并清除 `hasRemoteChange`、`hasConflict`
  - 若 `baseRuntimeSettingsVersion` 已推进且 authoritative runtime settings 与当前 dirty draft 不一致，则保持 dirty，标记 `hasConflict=true`
- `draft.manualAllocationDrafts` 增加基线元数据：
  - `editingConfigId`
  - `baseConfigId`
  - `baseConfigVersion`
  - `baseRuntimeVersion`
  - `hasRemoteChange`
  - `hasConflict`
  - `isOrphaned`
- dirty draft 规则与 query 页一致：
  - pristine draft 可自动跟随服务端更新
  - dirty draft 不得被 runtime event 直接覆盖
  - 服务端更新到达时默认只更新基线并标记 `hasRemoteChange`；只有本节下文定义的 matching authoritative settle 条件满足时，才允许转为 clean
  - 无法安全自动合并时标记 `hasConflict`
- `manualAllocationDrafts` 的 authoritative submit target 固定为 `editingConfigId`；`baseConfigId` 与 `baseConfigVersion` 用于校验该 draft 仍然建立在同一份配置基线上。
- `manualAllocationDrafts` 的唯一 seed / rebuild source 固定为当前 authoritative slices：`querySystem.configsById[ui.selectedConfigId]` + `purchaseSystem.runtimeStatus`。编辑器只能读取 draft 结果，不能在组件内直接拼接 server-owned 数据作为可编辑 payload。
- 若 `manualAllocationDrafts` 为 pristine，且当前 `selectedConfigId` 可解析到有效配置，则允许在 bootstrap、server update、clean switch、显式 discard 之后，按上述 seed source 自动重建 draft。
- 若存在 non-orphan 且 dirty 的 `manualAllocationDrafts`，用户主动切换 `ui.selectedConfigId` 时必须先弹出 leave-prompt。
- 选择“保存并切换”时，页面可以仅以局部 UI 态记录 `pendingSelectedConfigId`，但全局 `purchaseSystem.ui.selectedConfigId` 必须保持旧值；只有在对应 runtime event / resync 已落库，且当前 draft 不再 dirty 后，才允许真正切换 selection 并重建新 draft。
- manual allocation 保存请求发出后，编辑器进入 pending-save 态；在 authoritative event / resync 收口前，不允许继续修改同一 draft payload。
- 若后续 `purchase_runtime.updated` 或 resync bootstrap 为当前 `editingConfigId` 重建出的 authoritative draft 与“当前待提交 payload”语义一致，则 store 必须把该 dirty draft rebase 成 clean authoritative draft，并清除 `hasRemoteChange` / `hasConflict`。
- 若 authoritative event / resync 到达后，`baseConfigVersion` 或 `baseRuntimeVersion` 已推进，但 authoritative draft 与待提交 payload 不一致，则必须保持 dirty，标记 conflict，并禁止消费 `pendingSelectedConfigId`。
- `pendingSelectedConfigId` 的生命周期固定为：仅在用户选择 save-and-switch 时 set；仅在 authoritative settle 后消费；在 conflict、orphan、submit failure、用户取消、显式 discard、成功消费后必须立即 clear。
- `pendingSelectedConfigId` 的唯一 owner / clearer 固定为 Purchase 页面本地流程状态机；store reducer 只负责产出 `settle-ready` / `conflict` / `orphan` 这类 terminal signals，不直接持有或清空该字段。
- 在上述 leave-prompt 结束前，手动分配编辑区继续绑定 `editingConfigId`，不得静默改绑到新的 `ui.selectedConfigId`。
- 只要 `query_configs.updated` 或 `purchase_runtime.updated` 判定 `editingConfigId` 或 `baseConfigId` 已不再存在于当前配置树 / 当前运行时上下文，draft 就必须立即标记 `isOrphaned=true`、`hasConflict=true`，并保留 `editingConfigId`。
- 若当前选中配置被删除或失效：
  - `ui.selectedConfigId` 按收敛规则切换
  - 若 `manualAllocationDrafts` 仍绑定旧配置且为 dirty，则标记 `isOrphaned=true`、`hasConflict=true`
  - orphaned manual allocation draft 不得自动迁移到新配置
  - `editingConfigId` 固定保留为原配置 ID，直到用户显式丢弃
  - 用户只能显式丢弃后继续，禁止提交

补充约束：

- 购买页中的 `querySettingsDraft` 不纳入本轮全局 runtime store。
- 它仍然是页面局部设置弹窗态，但 seed source 固定为 `querySystem.configsById[purchaseSystem.ui.selectedConfigId]` 中当前配置的 query-setting / `mode_settings` 详情。
- `querySettingsDraft` 打开时必须同时记录局部基线：`baseConfigId` + `baseConfigVersion`。
- 保存 query settings / `mode_settings` 时，命令目标固定为 `baseConfigId`，并携带 `baseConfigVersion`；HTTP response 不得直接回写主 store，最终展示必须等待 `query_configs.updated` 或等价 resync snapshot。
- query settings 保存请求发出后，local modal 进入 pending-save 态；在 authoritative echo / resync 收口前，不允许继续修改同一 local draft payload。
- 弹窗打开期间若收到命中同一配置的 `query_configs.updated`：
  - local draft pristine 时，可按最新配置自动刷新并更新 `baseConfigVersion`
  - local draft dirty 且与当前待提交 payload 语义一致时，将 local draft settle 为 clean authoritative draft，更新 `baseConfigVersion`，并结束 pending-save
  - local draft dirty 但与当前待提交 payload 不一致时，不得直接覆盖用户输入；只允许把弹窗标记为 `hasRemoteChange=true`，必要时标记 `hasConflict=true`
- 若 `querySettingsDraft` 绑定的配置被删除，或用户尝试切换 `purchaseSystem.ui.selectedConfigId`：
  - local draft pristine 时，直接关闭并丢弃该局部 draft
  - local draft dirty 时，必须先经过 save/discard prompt；未完成前不得静默切换到新配置
- reconnect bootstrap / 强制 resync 对 `querySettingsDraft` 的语义与 `query_configs.updated` 等价：
  - snapshot 仍包含 `baseConfigId` 时，按 pristine 自动刷新 / dirty authoritative settle / mismatch conflict 处理
  - snapshot 已不包含 `baseConfigId` 时，local draft pristine 直接关闭并丢弃；dirty 标记 `isOrphaned=true`、`hasConflict=true`，禁用提交，仅允许显式丢弃
- matching authoritative echo / resync snapshot 到达后，query settings modal 的唯一收口为：settle 成 clean authoritative draft 并关闭；mismatch / stale base 则保持 dirty 或 orphan/conflict，绝不允许用 HTTP success 直接收窗。
- `querySettingsDraft` 的唯一 settle 执行者固定为 Purchase 页本地 modal controller；Section 8 reducer 只通过 `querySystem.configsById` / bootstrap-resync snapshot 提供 authoritative echo，不直接 mutate local modal state。
- 该状态继续作为页面局部设置弹窗状态处理，不参与本轮“主状态单一真源”改造。

## 8. 事件映射规则

前端需要一层统一的 event reducer。

映射规则固定如下：

- `bootstrap`
  - hydrate `bootstrap`
  - hydrate `querySystem` server-owned slices
  - hydrate `purchaseSystem` server-owned slices
  - 初始化 query / purchase 两侧 selection 收敛
  - 更新 query / purchase draft 基线，但不得覆盖 dirty draft
  - 若 `currentConfig` 为 dirty，且 snapshot 中同配置 authoritative config 与当前 dirty draft 语义一致，则将其 settle 为 clean authoritative draft；若基线已推进且不一致，则保持 dirty 并标记 conflict
  - 若 `currentConfig` 绑定的配置已不在 resync snapshot 中，则立即标记 orphan/conflict，并禁止静默改绑
  - 若 `purchaseSettingsDraft` 为 dirty，且 snapshot 中 authoritative runtime settings 与当前 dirty draft 语义一致，则将其 settle 为 clean authoritative draft；若基线已推进且不一致，则保持 dirty 并标记 conflict
  - 若 `manualAllocationDrafts` 当前不是 dirty / orphan，则按 §7.4 的 seed 规则初始化或重建该 draft
  - 若 snapshot 显示 `manualAllocationDrafts` 绑定配置已失效，则立即标记 orphan/conflict
  - 若 snapshot 对当前 `editingConfigId` 的 authoritative draft 与待提交 payload 语义一致，则将 dirty draft settle 为 clean authoritative draft，并向页面发出 `settle-ready` terminal signal；若页面持有 `pendingSelectedConfigId`，此时允许 consume-and-clear
  - 若 snapshot 与待提交 payload 不一致且基线已推进，则保持 dirty 并标记 conflict，并向页面发出 `conflict` terminal signal；若页面持有 `pendingSelectedConfigId`，页面必须 clear，且不得消费
- `query_configs.updated`
  - 整包替换 `querySystem.configsById` 与 `configOrder`
  - 按 §7.3 的规则收敛 `querySystem.ui.selectedConfigId`
  - 按 §7.4 的规则重新收敛 `purchaseSystem.ui.selectedConfigId`
  - 同步更新对应配置的 draft 基线，但不得直接覆盖 dirty draft
  - 若 `currentConfig` 对应配置仍有效且 draft 为 pristine，则以最新 authoritative config 重建 / 刷新 `currentConfig`，并清除 `draft.hasUnsavedChanges`
  - 若 `currentConfig` 对应配置仍有效且 draft 为 dirty，且 authoritative config 与当前 dirty draft 语义一致，则将其 settle 为 clean authoritative draft，并清除 `draft.hasUnsavedChanges`
  - 若 `currentConfig` 对应配置仍有效且 draft 为 dirty，但 `baseConfigVersion` 已推进且与当前 dirty draft 不一致，则保持 dirty 并标记 conflict
  - 若 `currentConfig` 对应配置已不存在，则标记 orphan/conflict，并禁止静默改绑
  - 若 `manualAllocationDrafts` 绑定配置仍有效且 draft 为 pristine，则按最新 `querySystem.configsById[selectedConfigId]` + `purchaseSystem.runtimeStatus` 重建 draft，并推进 `baseConfigVersion`
  - 若 `manualAllocationDrafts` 为 dirty，则只更新 `baseConfigVersion` 与远端变更 / 冲突标记，不得直接覆盖用户编辑 payload
  - 若 `manualAllocationDrafts.editingConfigId` 或 `baseConfigId` 不再存在于新配置树，则立即标记 `isOrphaned=true`、`hasConflict=true`，保留 `editingConfigId`，并禁止提交直到显式丢弃；该分支向页面发出 `orphan` terminal signal，若页面持有 `pendingSelectedConfigId`，页面必须 clear，且不得消费
- `query_runtime.updated`
  - 整包替换 `querySystem.runtimeStatus`
  - 按 §7.3 的规则重新收敛 `querySystem.ui.selectedConfigId`
- `purchase_runtime.updated`
  - 整包替换 `purchaseSystem.runtimeStatus`
  - 按 §7.4 的规则收敛 `purchaseSystem.ui.selectedConfigId`
  - 若 `manualAllocationDrafts` 绑定配置仍有效且 draft 为 pristine，则按最新 `querySystem.configsById[selectedConfigId]` + `purchaseSystem.runtimeStatus` 重建 draft，并推进 `baseRuntimeVersion`
  - 若 draft 仍绑定同一 `editingConfigId` 且为 dirty，且 authoritative draft 与待提交 payload 语义一致，则将该 draft settle 为 clean authoritative draft，并向页面发出 `settle-ready` terminal signal；若页面持有 `pendingSelectedConfigId`，此时允许后续消费
  - 若 draft 仍绑定同一 `editingConfigId` 且为 dirty，但 `baseRuntimeVersion` 已推进且 authoritative draft 与待提交 payload 不一致，则保持 dirty，标记 conflict，并向页面发出 `conflict` terminal signal；若页面持有 `pendingSelectedConfigId`，页面必须 clear
  - 其余 dirty 场景下，只更新 `baseRuntimeVersion` 与远端变更 / 冲突标记，不覆盖用户编辑 payload
  - 若 draft 绑定的配置已失效，则保持 `editingConfigId` 不变并标记 orphan/conflict
- `purchase_ui_preferences.updated`
  - 整包替换 `purchaseSystem.uiPreferences`
  - 按 §7.4 的规则重新收敛 `purchaseSystem.ui.selectedConfigId`
- `runtime_settings.updated`
  - 整包替换 `purchaseSystem.runtimeSettings`
  - 若 `purchaseSettingsDraft` 为 pristine，则以最新 authoritative runtime settings 刷新 draft 基线
  - 若 `purchaseSettingsDraft` 为 dirty，且 authoritative runtime settings 与当前 dirty draft 语义一致，则将其 settle 为 clean authoritative draft
  - 若 `purchaseSettingsDraft` 为 dirty，但 `baseRuntimeSettingsVersion` 已推进且 authoritative runtime settings 与当前 dirty draft 不一致，则保持 dirty 并标记 conflict
  - 其余 dirty 场景下，只更新基线与远端变更 / 冲突标记，不得直接覆盖用户编辑 payload
- `runtime.resync_required`
  - 不清空业务数据
  - 仅标记连接过期
  - 立即关闭当前 runtime stream，并提升连接代际
  - 执行一次强制 `/app/bootstrap`
  - 仅当 bootstrap 返回结果满足 §6.3 的 generation 与 version 门槛时允许覆盖 server-owned slices
  - bootstrap 完成后用新的 `version` 重新建立 runtime stream

runtime event 不得覆盖以下 slice：

- `querySystem.ui` 中除 `selectedConfigId` 外的字段
- `querySystem.draft` 中用户正在编辑的 payload 字段
- `purchaseSystem.ui` 中除 `selectedConfigId` 外的字段
- `purchaseSystem.draft` 中用户正在编辑的 payload 字段

允许由 event 驱动更新的字段仅限：

- `querySystem.ui.selectedConfigId`
- `purchaseSystem.ui.selectedConfigId`
- 各 draft 的基线字段、remote change 标记、conflict 标记
- 仅对具备 orphan 语义的 draft 允许更新 orphan 标记：`querySystem.draft.currentConfig`、`purchaseSystem.draft.manualAllocationDrafts`、本地 `querySettingsDraft`
- 仅在以下两类场景允许 authoritative 数据改写 draft payload：
  - draft 为 pristine 时的 authoritative refresh / rebuild
  - dirty draft 命中本 spec 明确定义的 matching authoritative settle 条件时的 clean settle

event 不得整包替换 UI/draft slice，也不得覆盖用户正在编辑的 payload 字段；但允许上述两类 authoritative refresh / settle。

显式 refresh 的唯一写入边界固定为：

- 页面允许发起“刷新 detail / 刷新设置”命令
- 该命令的 HTTP 返回值不得直接写入主 store
- HTTP 只负责告诉用户命令成功或失败
- `capacitySummary` 即使在显式刷新场景下也不得被 HTTP response 直接补写；它只能在 bootstrap / resync 时更新
- 主 store 只能等待以下回流更新：
  - `query_configs.updated`
  - `runtime_settings.updated`
  - `purchase_runtime.updated`

为避免 silent overwrite，所有保存类命令还必须携带基线信息：

- query 配置保存类命令携带 `baseConfigVersion` 或等价基线字段
- purchase 设置保存类命令携带 `baseRuntimeSettingsVersion` 或等价强 revision token
- manual allocation 提交命令必须携带 `editingConfigId`、`baseConfigId`、`baseConfigVersion`、`baseRuntimeVersion` 或等价强 revision token
- 后端必须同时校验：
  - 请求目标配置身份等于 `editingConfigId`
  - draft 基线身份仍与 `baseConfigId` 一致
  - draft 基线配置版本仍与 `baseConfigVersion` 一致
  - `baseRuntimeVersion` 未过期
- 任一校验不满足时，后端必须返回 conflict；前端不得静默覆盖

视图读源所有权矩阵固定如下：

- Query 配置导航 / 列表 / 运行态摘要：只读 `querySystem.configsById`、`querySystem.configOrder`、`querySystem.runtimeStatus`
- Query 配置编辑表单：只读 `querySystem.draft.currentConfig`
- Purchase 运行态摘要 / 账号列表 / 商品列表：只读 `purchaseSystem.runtimeStatus`
- Purchase 当前配置展示：只读 `querySystem.configsById` + `purchaseSystem.ui.selectedConfigId`
- Purchase 手动分配编辑区：优先只读 `purchaseSystem.draft.manualAllocationDrafts`，禁止直接把 `purchaseSystem.runtimeStatus.item_rows` 当可编辑源
- Purchase 手动分配 draft 的创建 / 重建：只能由 reducer/action 按 §7.4 的 seed 规则生成，禁止在组件内临时从 server-owned slice 拼接
- Purchase orphan manual allocation 场景：
  - banner / 禁提态只读 `purchaseSystem.draft.manualAllocationDrafts`
  - 其渲染与提交键一律使用 `editingConfigId`
  - 不得回退绑定到新的 `selectedConfigId`
- Purchase 设置编辑表单：只读 `purchaseSystem.draft.purchaseSettingsDraft`
- Purchase 查询设置弹窗：打开时从 `querySystem.configsById[purchaseSystem.ui.selectedConfigId]` seed 本地 `querySettingsDraft`，保存后最终展示只认 `query_configs.updated` 或等价 resync snapshot

凡是存在 draft 的可编辑界面，禁止直接读取对应 server-owned 字段作为编辑值来源。

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

补充硬约束：

- query config 保存后的 dirty/pending 只允许由 matching `query_configs.updated` 或等价 resync snapshot settle 为 clean
- query config 保存遇到 stale base / mismatch 时，只允许转 conflict/orphan；HTTP success 不得直接清 `draft.hasUnsavedChanges`

显式 detail refresh 的语义固定为：

- 允许用户触发后端刷新
- 不允许 query 页用 HTTP 响应直接 patch `currentConfig`
- 刷新后的最终配置内容必须以 `query_configs.updated` 回流为准
- Query 命令成功后，页面不得直接 patch 任意 `querySystem.*` slice

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
  - 查询设置弹窗的本地编辑态
  - leave-prompt / `pendingSelectedConfigId` 这类纯 UI 过程态

其中“配置相关状态”的真源固定为：

- `querySystem.configsById`
- `querySystem.configOrder`
- `purchaseSystem.ui.selectedConfigId`
- `purchaseSystem.uiPreferences`

Purchase 页面补充硬约束：

- 任何 purchase 命令成功后，页面不得直接 patch 任意 `purchaseSystem.*` 或 `querySystem.*` slice
- `querySettingsDraft` 仅是弹窗局部 draft，不得作为主渲染真源；打开时从 `querySystem` 当前配置 seed，并携带 `baseConfigVersion`
- `querySettingsDraft` 在保存成功后也不得直接 patch 展示；任何保存/刷新后的最终配置展示都必须等待 `query_configs.updated` 或等价 resync snapshot 回流
- `querySettingsDraft` 若在打开期间收到同配置普通远端更新，pristine 可自动刷新；dirty 只允许标记 local remote-change/conflict，不自动关窗
- `purchaseSettingsDraft` 的 dirty/pending 只允许由 matching `runtime_settings.updated` 或等价 resync snapshot settle 为 clean；HTTP success 不得直接清 dirty / pending-save
- 当 `manualAllocationDrafts` 为 dirty 且非 orphan 时，用户主动切换配置必须先经过 discard/save prompt；在对应 event / resync 落库前，不得切换 `purchaseSystem.ui.selectedConfigId`
- 当 `manualAllocationDrafts` 为 pristine，或用户已显式 discard 旧 draft 后，页面必须立刻按 §7.4 seed 规则为新的 `selectedConfigId` 重建 manual allocation draft
- `pendingSelectedConfigId` 由 `use_purchase_system_page.js` 这类页面流程持有；只有在 store 已把当前 manual allocation draft settle 为 clean authoritative draft 后，页面才允许消费该值并真正切换 selection；在 conflict、orphan、submit failure、用户取消、显式 discard、成功消费后必须清空
- `pendingSelectedConfigId` 的 set / consume / clear 只允许发生在 Purchase 页本地流程状态机中；Section 8 reducer 只输出 terminal signals，不直接操作该字段
- `querySettingsDraft` 的 seed / settle / close / orphan / conflict 也只允许发生在 Purchase 页本地 modal controller 中；Section 8 reducer 不直接操作该 local draft
- 最终状态只能来自：
  - `query_configs.updated`
  - `purchase_runtime.updated`
  - `purchase_ui_preferences.updated`
  - `runtime_settings.updated`
  - 必要时的 resync bootstrap

## 10. 非目标

本轮设计明确不做：

- renderer reload 后恢复上次状态
- 本地落盘 runtime 快照
- 诊断面板实时推送化
- 将所有 UI 小状态都搬入全局 store

## 11. 实施顺序

按以下顺序落地，禁止穿插大范围同时修改：

1. 为 `/ws/runtime` 客户端补测试，再接通 runtime stream client
2. 先统一定义并测试 `version / connectionGeneration / bootstrap 门控` 语义，再同步改造 `runtime_connection_manager` 与 `app_runtime_store`
3. 为 `selection 收敛 / dirty draft 基线 / conflict 标记` 补测试，再扩展 store
4. 为 query 页“只读 store + 显式命令”路径补测试，再删除 query 页主数据 fetch
5. 为 purchase 页“无 polling、无 preview fallback、跨页 draft 保留”路径补测试，再删除 purchase 页主数据 fetch 与 polling
6. 在前述测试全部通过后，删除冗余 hydration、补拉、fallback 旧路径
7. 最后统一清理废弃测试与过时辅助代码

## 12. 测试策略

至少补齐以下验证：

### 12.1 connection manager

- bootstrap 后建立 runtime stream
- 接收 `query_runtime.updated` 会更新 store
- 接收 `purchase_runtime.updated` 会更新 store
- 接收 `runtime.resync_required` 会强制 bootstrap
- socket 断开后业务数据保留，连接态变 stale
- 旧连接代际的迟到 event 会被丢弃
- `version <= lastEventVersion` 的重复或低版本 event 会被丢弃
- 旧 generation 的 bootstrap 晚到结果会被丢弃
- `resync_required@R` 触发的 bootstrap 只有 `version >= R` 时才允许落库
- 普通 reconnect bootstrap 在 `version == lastEventVersion` 时也允许恢复连接
- bootstrap 与其后 ws 共享同一 generation，不会在两者之间再次 bump

### 12.2 runtime store

- runtime event 映射正确
- `query_configs.updated` 可覆盖完整配置树
- event 不整包替换 UI / draft slice，也不覆盖用户正在编辑的 payload；但允许 pristine refresh 和 matching authoritative settle
- resync 只更新连接状态与 bootstrap，不回退到空视图
- 删除当前选中配置后，selection 会按规则收敛
- dirty draft 遇到服务端更新时默认仅更新基线，不直接覆盖编辑内容；只有 matching authoritative settle 条件满足时才允许转 clean
- conflict / remote change 标记会正确设置
- bootstrap 后 query / purchase 两侧 selection 会立即初始化
- `query_configs.updated` 会同步驱动 purchase selection 收敛
- bootstrap / resync 会更新 draft 基线但不覆盖 dirty draft
- 删除选中配置后，query / purchase orphan draft 会按规则标记并阻止静默迁移
- `capacitySummary` 仅作为 advisory reference slice，不参与 runtime correctness 判定
- `capacitySummary` 不会被显式 refresh 的 HTTP response 直接补写
- `purchase_runtime.updated` 会推进 `manualAllocationDrafts.baseRuntimeVersion` 与 orphan/conflict 标记
- `query_configs.updated` 会推进 `manualAllocationDrafts.baseConfigVersion`，并在 pristine 场景下触发重建
- `query_configs.updated` 删除 `manualAllocationDrafts.editingConfigId/baseConfigId` 对应配置时，会立即标记 orphan/conflict 并禁止提交
- matching `query_configs.updated` / resync snapshot 会把 `currentConfig` dirty draft settle 为 clean；stale base / mismatch 只会产生 conflict/orphan，不会静默清 dirty
- matching `runtime_settings.updated` / resync snapshot 会把 `purchaseSettingsDraft` dirty draft settle 为 clean；stale base / mismatch 只会产生 conflict，不会静默清 dirty
- matching `purchase_runtime.updated` / resync 会把 manual allocation dirty draft settle 为 clean；stale base / mismatch 只会产生 conflict，不会静默清 dirty
- `purchase_runtime.updated` 是 manual allocation save-and-switch 的唯一 event settle 路径；resync bootstrap 为等价兜底路径，`query_configs.updated` 不得 settle save-and-switch，也不得消费 `pendingSelectedConfigId`
- reducer 对 manual allocation 只负责输出 `settle-ready` / `conflict` / `orphan` terminal signals；页面本地流程状态机负责消费这些 signals 并 set/consume/clear `pendingSelectedConfigId`
- 四类 draft/editor 的 settle clean 都必须经过唯一共享的 canonical comparator/helper 判定，禁止各处自定义 deep-compare / ad-hoc compare

### 12.3 页面行为

- 切换 query 页不再重新拉主数据
- 切换 purchase 页不再重新拉主数据
- purchase 页不再依赖 preview fallback 作为主展示
- 断线后保留最后有效数据
- 恢复后通过 resync 或后续 event 追平
- query 页显式 refresh detail 不再直接 patch store
- query config 保存后的 HTTP 200 不会直接清 `currentConfig` dirty；只有 `query_configs.updated` 或等价 resync snapshot 才能 settle clean
- purchase 页配置读取统一来自 `querySystem` 真源
- 跨页应保留的 `selectedConfigId` 与 draft 在切页后仍保留
- purchase 页的 HTTP 响应不会直接 patch 主 store
- purchase settings 保存后的 HTTP 200 不会直接清 `purchaseSettingsDraft` dirty；只有 `runtime_settings.updated` 或等价 resync snapshot 才能 settle clean
- 查询设置弹窗本地编辑态不进入 runtime 主状态真源，但会从 `querySystem` 当前配置 seed，并携带 `baseConfigVersion`
- 查询设置弹窗打开期间若收到同配置普通远端更新，pristine 自动刷新；dirty 只提示 local remote-change/conflict，不自动关窗
- 查询设置弹窗绑定配置被删除，或用户尝试切换配置时，pristine 自动关闭；dirty 必须先经过 save/discard prompt
- 查询设置弹窗在 reconnect bootstrap / resync 后仍遵循同一套 seed / conflict / orphan 规则，不得悬挂在过期 baseline 上
- query settings 保存后的 matching `query_configs.updated` / resync snapshot 会把 local modal settle 为 clean authoritative draft 并关闭；mismatch / stale base 只会导向 conflict 或 orphan
- query / purchase 编辑界面均只读各自 draft，不混读 server-owned 可编辑字段
- 页面本地 pending 态不承载业务 shadow data
- purchase orphan manual allocation 会保留 `editingConfigId`，显示冲突 banner，并禁止提交直到显式丢弃
- purchase 页存在 dirty 且 non-orphan 的 manual allocation draft 时，主动切换配置会先触发 leave-prompt；未等到 event / resync 落库并完成重建前 selection 不变
- purchase 页在 clean switch 或 discard 后，会立即按 authoritative slices 重建新的 manual allocation draft
- stale `baseConfigVersion` / `baseRuntimeVersion` 的保存会返回 conflict；冲突后 draft/modal 保持 dirty，不得静默切换或清空
- save-and-switch pending 期间，manual allocation 请求目标仍冻结在旧 `editingConfigId`，直到 authoritative settle 后才允许消费 `pendingSelectedConfigId`
- `pendingSelectedConfigId` 在 submit failure、用户取消、orphan、显式 discard、conflict、成功消费后都会立即 clear
- `querySettingsDraft` 打开后，其保存目标始终冻结在 `baseConfigId`；HTTP 200 不能直接完成最终展示，最终展示只能等 `query_configs.updated` 或等价 resync snapshot
- `querySettingsDraft` 与 `pendingSelectedConfigId` 的 settle / close / clear 都只发生在 Purchase 页本地状态机中；store reducer 只提供 authoritative echo 与 terminal signals

## 13. 验收标准

本轮完成标准为：

1. remote 模式下 `App` 启动后会建立 `/ws/runtime`
2. query / purchase 页面切换时不再出现主内容回默认态
3. purchase 页不再依赖 preview fallback 伪装数据
4. 断线时页面保留最后一次有效业务态
5. 恢复连接后状态可以自动 resync
6. 旧 socket 的迟到 event 与低版本 event 不会导致状态倒退
7. `selectedConfigId` 在配置删除或重排后会按规则自动收敛
8. query / purchase 的 dirty draft 在 bootstrap、event、resync 后不会被误覆盖
9. query 页显式 refresh detail 不会重新打开第二条主状态写入路径
10. 页面主状态真源可以明确解释为：
   - 首次 `/app/bootstrap`
   - 运行时 `/ws/runtime`
11. HTTP 在本轮架构中只作为命令触发器，不作为主状态真源
12. 旧 generation 的 bootstrap 与 event 都不会导致状态倒退
13. 普通断线重连在“无新版本变化”时也能恢复连接，不会永久停在 `stale`
14. query / purchase 的 orphan draft 会被显式标记，不会静默跟随 selection 改绑
15. purchase 页 `querySettingsDraft` 始终只是局部 editor draft；其 seed、保存和冲突判定都绑定 `querySystem` 当前配置与 `baseConfigVersion`
16. purchase 页在 clean switch、discard、save-and-switch 后，都能基于 authoritative slices 重建正确的 manual allocation draft，且不会出现 `selectedConfigId` 已切换但编辑器仍无定义来源的状态
17. purchase 页的 save-and-switch 只会在对应 event / resync 落库后才真正提交 selection 切换，不会因为 HTTP 200 提前切换到新配置
18. stale `baseConfigVersion` / `baseRuntimeVersion` 只会导向 conflict，不会通过本地比较或 HTTP success 被静默清掉
19. `querySettingsDraft` 的保存目标始终冻结在 `baseConfigId`，最终展示只能由 `query_configs.updated` 或等价 resync snapshot 完成
20. save-and-switch pending 期间，manual allocation 的提交目标始终冻结在旧 `editingConfigId`；只有 authoritative settle 后才允许切到新的 `selectedConfigId`
21. `pendingSelectedConfigId` 的生命周期是 `set -> authoritative settle consume -> clear`，并且在 conflict、orphan、submit failure、用户取消、显式 discard 时也会立即 clear
22. query settings 保存后的 authoritative echo 只允许两种结果：match 则 settle clean 并关闭 modal；mismatch / stale base 则转 conflict 或 orphan，绝不允许 HTTP success 直接收窗
23. query config editor 遵循 authoritative-settle contract：match 则 settle clean；mismatch / stale base 则转 conflict/orphan；HTTP success 永远不直接清 pending/dirty
24. purchase settings editor 遵循 authoritative-settle contract：match 则 settle clean；mismatch / stale base 只会转 conflict；HTTP success 永远不直接清 pending/dirty
25. manual allocation save-and-switch 只允许 `purchase_runtime.updated` 或等价 resync bootstrap settle；`query_configs.updated` 不得消费 `pendingSelectedConfigId`
26. `pendingSelectedConfigId` 与 `querySettingsDraft` 的唯一 owner 都是 Purchase 页本地状态机；store reducer 只输出 authoritative echo 与 terminal signals，不直接 clear local state
27. 四类 draft/editor 的 settle clean 都允许 canonical comparator，但只能通过唯一共享 helper 判定；禁止各处自定义 deep-compare

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
