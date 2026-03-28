# Managed Browser Account Session Design

> Historical note (2026-03-28): `ManagedProfileSeed` / `Tampermonkey` was a candidate design branch only and is now considered abandoned. The current active implementation does not provision Tampermonkey or a seed-profile chain; it uses managed runtime plus per-account `browser-profiles` / cloned `browser-sessions`.

## 1. 目标

在当前前后端分层架构下，把登录链路从“依赖用户本机默认 Edge profile 的 attach 模式”和“临时 Selenium profile 模式”进一步收口成统一的受管浏览器方案，同时满足以下目标：

- 登录时始终使用全新浏览器会话，避免不同账号互相污染
- 登录完成后必须经过一次刷新验真，只有刷新后仍在线才算成功
- 登录成功后把该账号的会话材料持久化保存，后续可无缝切换多个账号
- 运行时尽量不依赖用户机器预先安装 Edge
- 代理登录能力进入统一浏览器启动器，而不是继续维护完全独立的旧链

本次设计的核心不是“把所有登录行为塞进一个永续浏览器”，而是把“登录浏览器”和“账号会话资产”拆成两个不同层级：

- 登录浏览器：一次性、干净、可销毁
- 账号会话资产：持久化、可切换、按账号隔离

## 2. 非目标

本次设计明确不追求：

- 直接保留用户本机真实 Edge `Default` profile 作为长期运行依赖
- 继续把“扫码成功即任务成功”作为唯一判定
- 让一个已登录浏览器窗口长期承载所有账号切换
- 让前端 UI 一次性暴露全部高级会话管理操作

这次只收口登录与会话资产管理，不同时推进无关 UI 重构。

## 3. 约束

必须遵守以下硬约束：

- 通过率优先于“绝对从零画像”
- 登录完成后必须刷新目标页面做二次验真
- 每次重新登录必须从新的浏览器会话开始，不能复用上一个账号的浏览器现场
- 一个账号重新登录时，只覆盖该账号自己的会话资产，不能污染其他账号
- 后续多账号切换要基于“账号会话资产”切换，而不是要求用户重新扫码
- 代理能力必须进入统一启动器，不能再让直连和代理维持两套长期分裂的浏览器架构

## 4. 当前问题

当前已验证成功的直连登录链，本质上依赖以下事实：

- 使用真实 Edge 环境而不是 Selenium 临时 profile
- 附着到了用户机器上已有的真实浏览器 profile
- 当时曾依赖真实 profile 中已有的 Tampermonkey 与反调试脚本
- attach 模式下跳过了页面监控注入，减少了被站点检测到的概率

这条链解决了当前滑块问题，但仍有结构性缺陷：

1. 依赖用户机器已安装并可正常启动的 Edge
2. 依赖用户当前机器上的特定 profile 环境，不便交付给其他用户
3. 同一个真实 profile 内的历史账号状态会残留，不利于账号隔离
4. 代理账号仍保留旧的临时 Selenium profile 启动链，系统存在双轨运行
5. 当前持久化的主要是 `cookie_raw` 等接口侧材料，尚未形成真正的“账号会话资产”层

## 5. 方案比较

### 方案 A：继续依赖系统 Edge attach，仅做少量补丁

- 主程序继续附着用户本机 Edge
- 只优化 cookie 保存与账号切换

优点：

- 现有通过率最高
- 短期改动最小

缺点：

- 仍依赖用户机器环境
- 无法保证账号隔离
- 不适合封装后分发给其他用户
- 代理链仍无法统一

### 方案 B：每次完全空白浏览器 + 只保存 cookie/token

- 程序自带浏览器 runtime
- 每次登录都从完全空白 profile 启动
- 只保存接口所需 cookie/token

优点：

- 环境最干净
- 存储最轻

缺点：

- 滑块通过率风险最高
- 浏览器侧状态不完整，刷新或重新开浏览器时稳定性弱
- 很可能需要反复补漏 `localStorage` 等状态

### 方案 C：受管浏览器 runtime + 母体 seed profile + 每次克隆新 session + 账号会话资产封存（历史候选，已废弃）

- 程序自带受管浏览器 runtime
- 程序维护一份不含最终用户登录态的母体 seed profile
- 每次登录前，从 seed 克隆出一个全新临时 session 目录
- 登录成功并刷新验真后，导出该账号的会话资产并持久化保存
- 后续多账号切换以账号会话资产为中心

优点：

- 兼顾通过率与账号隔离
- 不依赖用户本机已有 profile
- 可以把 Tampermonkey、脚本、必要扩展和代理能力统一纳入受管环境
- 登录与账号切换可以形成清晰分层

缺点：

- 比继续 attach 系统 Edge 更复杂
- 需要新增 runtime 管理、seed profile 管理和会话资产仓储

## 6. 结论

本文当时选择方案 C，但该 `seed profile + Tampermonkey` 分支最终未落地，现已废弃。

原因：

- 这是唯一同时满足“通过率优先”“重新登录时全新浏览器”“登录后刷新必须通过”“会话可按账号长期保存并切换”“适合后续分发”的方案
- 它把“浏览器环境稳定性”和“账号会话隔离”拆开治理，避免两者互相拖死
- 它为直连和代理提供了共同的浏览器启动底座

## 7. 总体架构

新设计拆成 5 个清晰单元：

### 7.1 `ManagedBrowserRuntime`

职责：

- 定位或安装程序自带浏览器 runtime
- 提供受管浏览器可执行文件路径
- 校验 runtime 版本与启动能力

说明：

- 首选“程序自带受管 runtime”
- 若未来要直接分发 Microsoft Edge 二进制，需要额外做分发与许可确认；当前设计不把某一厂商二进制写死到实现承诺中

### 7.2 `ManagedProfileSeed`（历史候选，未实现）

职责：

- 保存一份“高通过率基础环境”母体 profile
- 预装 Tampermonkey、反调试脚本、必要扩展、基础偏好
- 严禁保存最终用户账号登录态

说明：

- 它是“环境模板”，不是“某个账号的 profile”
- 它可以长期保留，因为通过率优先
- 它只能由受管 seed 构建/升级流程更新，登录流程本身无权回写 seed

### 7.3 `EphemeralLoginSession`

职责：

- 每次登录前从 `ManagedProfileSeed` 克隆出一个新的临时 session
- 按需要注入代理配置
- 拉起登录浏览器并完成扫码、跳转、刷新验真
- 登录完成后导出账号会话资产

说明：

- 这是一次性对象
- 登录完成后可销毁，不长期持有

### 7.4 `AccountSessionBundleRepository`

职责：

- 按账号持久化保存该账号的会话资产
- 支持读取、覆盖、删除、版本迁移
- 允许后续恢复为接口运行态或浏览器恢复态

它不是普通配置仓库，而是“凭据仓库 + 状态仓库”，因此必须具备以下生命周期：

- `staged`
  登录任务已导出原始会话资产，但尚未完成刷新验真与账号归属
- `verified`
  已通过刷新验真，但仍等待最终账号归属
- `active`
  已原子绑定到某个账号，供运行时读取
- `superseded`
  被更新 bundle 替换，不再对运行时可见
- `deleted`
  已丢弃或随账号删除

仓储必须满足：

- per-account single-writer：同一账号任一时刻只能有一个 bundle 激活写入者
- atomic replace：新 bundle 必须完整写入后再替换旧 bundle
- read isolation：运行时只能读取 `active` 版本，不能读到 `staged` 或半成品
- deterministic cleanup：任务取消、冲突驳回、导出失败时必须清理其 `staged/verified` bundle

### 7.5 `SessionSwitchService`

职责：

- 在多个账号间无缝切换
- 运行时需要哪个账号，就装载哪个账号的会话资产
- 某个账号失效时，只重登该账号并覆盖其 bundle

### 7.6 `LoginExecutionResult`

职责：

- 承载一次登录任务的内部执行结果
- 同时向上层提供“兼容旧登录链需要的账号信息”和“新会话资产链需要的 staged bundle 引用”

说明：

- 外部 HTTP API、任务事件流和前端交互保持不变
- 但后端内部不再把 `LoginCapture` 视为唯一登录产物
- `LoginCapture` 成为 `LoginExecutionResult` 中的兼容字段，而不是全部语义

## 8. 登录成功判定

登录成功判定必须从现在的“扫码完成/跳转成功”升级为四段式：

1. 成功进入登录后目标页
2. 成功抓到用户身份信息
3. 主动刷新目标页一次
4. 刷新后仍能确认在线身份与可用会话

只有四步全部通过，才允许：

- 标记任务成功
- 回写账号信息
- 保存 `AccountSessionBundle`

如果刷新后掉线、身份缺失或关键存储材料丢失，则本次登录判定为失败，不落库。

### 8.1 刷新验真标准

“刷新验真成功”必须满足以下可执行标准：

- 浏览器刷新 `https://www.c5game.com/user/user/`
- 从刷新开始计时，10 秒内至少命中一个成功探针

成功探针：

1. 网络探针成功
   `/api/v1/user/v2/userInfo` 返回成功，且 `userId` 与扫码阶段捕获的用户一致

2. 页面探针成功
   当前 URL 仍位于 `/user/user/`，且页面或脚本可提取到同一 `userId`

并且还必须同时满足：

- 关键 cookie 仍存在
- 会话材料可导出

失败条件：

- 10 秒内无成功探针
- 探针返回了不同账号
- 刷新后跳回登录页
- 关键 cookie 或会话材料缺失

第一阶段的“关键 cookie”最低要求为：

- `NC5_deviceId`
- 若存在 access token 体系，则 token 相关 cookie 不得在刷新后丢失

## 9. `AccountSessionBundle` 保存粒度

本次设计不采用“只存 cookie”这种过窄粒度，而是定义统一的账号会话资产包。

为控制第一阶段范围，bundle 分为两层：

### 9.1 v1 mandatory

- `bundle_id`
- `account_id`
- `scanned_user_id`
- `captured_at`
- `browser_runtime_id`
- `seed_profile_version`
- `bundle_schema_version`
- `cookie_raw`
- `cookies[]`
- `token_material`
- `local_storage_snapshot`
- `capture_quality`
- `refresh_verified`
- `login_probe`

### 9.2 future optional

- `session_storage_snapshot`
- `indexeddb_manifest`
- `restorable_browser_state`

说明：

- `cookies[]` 用于结构化恢复
- `token_material` 用于接口侧直接调用
- `local_storage_snapshot` 是 v1 必须项，因为仅靠 cookie 不稳定
- `session_storage_snapshot`、`indexeddb_manifest`、`restorable_browser_state` 收敛到后续阶段，避免 v1 范围膨胀
- `account_id` 在 `staged/verified` 阶段可以为空；最终激活时才绑定目标账号
- `scanned_user_id` 用于冲突处理与账号归属判定

## 10. 登录流程新数据流

### 10.1 发起登录

1. 用户在当前账号上点击登录
2. 后端创建登录任务
3. `ManagedBrowserRuntime` 解析受管浏览器 runtime
4. `EphemeralLoginSession` 从 `ManagedProfileSeed` 克隆新的临时 session
5. 如账号配置了代理，则在该临时 session 中注入代理配置
6. 启动浏览器并进入登录页

### 10.2 验真与导出

1. 用户完成扫码
2. 系统判定进入目标页
3. 系统抓取用户身份与 cookie/token
4. 系统主动刷新目标页
5. 刷新后再次确认用户仍在线
6. 导出浏览器存储并组装 `staged bundle`
7. 生成 `LoginExecutionResult`，其中至少包含：
   - 兼容字段：`LoginCapture`
   - 新字段：`staged_bundle_id`
   - 验真字段：`refresh_verified`
8. 若扫码账号与当前账号不一致，则进入冲突处理；此时 bundle 只能停留在 `verified`，不得直接绑定账号
9. 只有在账号归属最终确定后，才允许把 `verified bundle` 原子提升为目标账号的 `active bundle`

### 10.3 收尾

1. 登录任务落库成功
2. 临时登录浏览器关闭
3. 该临时 session 删除
4. 若归属决策成功，则目标账号切换到新的 `active bundle`
5. 若归属决策失败或用户取消冲突处理，则删除本次 `staged/verified bundle`

## 11. 运行时多账号切换

多账号切换不再等价于“切浏览器窗口”，而是切换账号会话资产。

### 11.1 接口运行态

当查询/购买运行时只需要接口材料时：

- 直接从 `AccountSessionBundle` 读取 `cookie_raw` / `token_material`
- 不需要重新打开浏览器

### 11.2 浏览器恢复态

当后续某些能力必须重新打开浏览器时：

- 从该账号 bundle 还原结构化 cookies 与存储快照
- 恢复到新的临时浏览器上下文中
- 该浏览器实例仍只服务于当前账号

### 11.3 失效重登

若某账号会话失效：

- 只为该账号重新创建新的 `EphemeralLoginSession`
- 登录成功后以原子替换方式覆盖该账号原有 `active bundle`
- 不触碰其他账号 bundle

## 12. 代理方案

代理必须进入统一启动器，不再维护“直连一套、代理另一套”的长期分裂架构。

设计要求：

- 直连与代理都使用同一套受管浏览器 runtime
- 代理配置注入发生在 `EphemeralLoginSession` 层
- 代理实现优先选择可与受管 seed/profile 共存的方式
- 不允许因为代理而回退到完全不同的旧登录架构

第一阶段允许保留两种代理注入方式：

- 参数化代理
- 受管扩展代理

但无论底层采用哪种注入方式，对上层都应表现为统一的 `EphemeralLoginSession(proxy=...)`。

## 13. 存储与清理策略

### 13.1 长期保留

长期保留的有三类资产：

- 受管浏览器 runtime
- `ManagedProfileSeed`
- 每个账号的 `AccountSessionBundle`

### 13.2 一次性资产

以下资产必须在登录完成后销毁：

- 临时 session profile 目录
- 临时代理插件目录
- 一次性调试端口状态

### 13.3 账号隔离原则

- 任何登录后生成的用户状态，不回写到 seed profile
- 任何一个账号的 bundle，不可被另一个账号直接复用
- 删除某账号时，应支持连带删除其 bundle

## 14. 会话资产安全边界

`AccountSessionBundle` 本质上属于高敏感本地凭证材料。

因此设计必须满足：

- 不把 bundle 明文打印到任务日志
- 不把 bundle 通过调试事件广播给前端
- 仓储层读写时只暴露必要字段
- 删除账号时支持同步删除 bundle
- 导出失败时不得留下半成品 bundle 文件
- bundle 文件必须落在应用私有目录，不能散落在临时工作目录
- 默认启用 encryption-at-rest；Windows 上优先使用当前用户上下文可解的本地保护机制
- bundle 文件权限默认收敛到当前应用用户可读写
- 日志、事件和诊断输出中只允许出现脱敏后的 bundle 元数据，不允许出现原始凭据内容

实现必须预留以下扩展点：

- bundle 序列化钩子
- bundle 加密/解密钩子
- bundle 版本升级钩子

## 15. 错误处理

至少需要覆盖以下失败场景：

1. 受管浏览器 runtime 不存在或损坏
2. seed profile 缺失或版本不兼容
3. 浏览器启动失败
4. 代理注入失败
5. 扫码超时
6. 已跳转但抓不到用户身份
7. 第一次登录成功但刷新后掉线
8. 会话资产导出不完整
9. bundle 保存失败
10. bundle 恢复失败

错误分层原则：

- 运行时/安装问题：明确报给用户并阻止继续登录
- 登录行为问题：标记当前任务失败，不覆盖旧 bundle
- 导出/保存问题：视为本次登录未完成，不得写入半成品 bundle

## 16. 与当前代码的集成方向

本设计不要求推翻当前后端任务流，而是在现有边界下替换底层执行链。

保持不变的边界：

- `app_backend/workers/tasks/login_task.py`
- 账号保存、冲突处理、任务事件模型
- 外部 HTTP API、前端交互和任务事件名称

需要新增或重构的方向：

- 当前登录执行器已进一步收口为受管浏览器登录执行器；现行代码入口位于 `app_backend/infrastructure/browser_runtime/login_adapter.py` 中的 `ManagedEdgeCdpLoginRunner`
- `login_adapter.py` 的内部返回值允许从单一 `LoginCapture` 演进为 `LoginExecutionResult`
- 新增 runtime 管理模块
- 新增 seed profile 管理模块
- 新增账号会话资产仓储
- 登录成功后增加刷新验真与资产导出

## 17. 与现有账号数据的兼容策略

当前系统中已经存在只保存 `cookie_raw` / `api_key` 的账号数据。

兼容原则：

- 不要求一次性把所有旧账号批量迁移为 bundle
- 旧账号在没有 bundle 时，继续按现有可用材料运行
- 某旧账号下一次重新登录成功后，再为该账号生成首个 bundle
- 运行时优先读取 bundle；若 bundle 缺失，再回退读取旧字段
- 若 bundle 的 schema/runtime/seed 版本不兼容，则浏览器恢复态禁用，并要求重新登录生成新 bundle

这样可以保证：

- 本次架构升级不需要一次性清洗全量账号
- 不会因为引入 bundle 而让现有账号立即失效

## 18. 版本兼容矩阵

bundle 的恢复能力不能只靠“字段里记了版本号”就结束，必须定义兼容规则。

### 18.1 版本维度

- `bundle_schema_version`
- `browser_runtime_id`
- `seed_profile_version`

### 18.2 兼容规则

- `bundle_schema_version` 不兼容：
  禁止读取该 bundle，必须迁移或重登
- `browser_runtime_id` 仅次版本变化：
  允许接口运行态继续使用，浏览器恢复态按探针验证后启用
- `browser_runtime_id` 主版本变化：
  默认禁用浏览器恢复态，必要时要求重登
- `seed_profile_version` 变化：
  不影响接口运行态；浏览器恢复态需通过兼容探针，否则要求重登

### 18.3 升级策略

- 仓储读取时先做版本判定
- 可自动迁移的只迁移 schema
- runtime/seed 不兼容时，不做隐式修补，直接显式提示“需重新登录”

## 19. 迁移策略

建议分三阶段迁移：

### 阶段 1：建立受管浏览器 runtime 与 seed profile

- 引入程序自带受管 runtime
- 把高通过率环境沉淀为受管 seed
- 保持现有登录任务入口不变

### 阶段 2：登录后刷新验真与 bundle 导出

- 登录成功后强制刷新
- 通过后导出 `AccountSessionBundle`
- 账号改为以 bundle 为核心资产

### 阶段 3：多账号切换与浏览器恢复态

- 运行时可直接切换 bundle
- 按需要支持从 bundle 恢复浏览器态
- 代理能力完全并入统一启动器

## 20. 测试策略

### 20.1 登录执行器测试

至少覆盖：

- 每次登录都创建新的临时 session
- 登录成功后必须执行一次刷新
- 刷新失败时任务判失败
- 成功时导出 bundle
- 登录结束后清理临时 session
- 刷新验真命中网络探针与页面探针两条路径
- 扫码账号与当前账号不一致时，bundle 进入 `verified` 而不是直接激活

### 20.2 Bundle 仓储测试

至少覆盖：

- 新账号 bundle 保存
- 同账号重登覆盖原 bundle
- 删除账号时删除 bundle
- 恢复时结构化 cookies / 存储快照完整
- 只读方永远读不到 `staged` 半成品
- 同账号并发写入时只有一个 writer 能完成激活

### 20.3 多账号切换测试

至少覆盖：

- A/B 账号 bundle 可独立读取
- 切换账号不串 cookie
- A 账号失效重登不影响 B 账号

### 20.4 代理链回归

至少覆盖：

- 直连与代理都走统一启动入口
- 代理异常时不污染非代理账号 bundle

## 21. 成功标准

该设计落地后，至少应满足：

- 用户机器未预装 Edge 时，程序仍可完成登录
- 任意账号重新登录都从新的浏览器会话开始
- 登录成功必须经过刷新验真
- 每个账号都拥有独立持久化会话资产
- 后续切换账号不要求重新扫码
- 某账号重登不会污染其他账号
- 代理登录不再依赖独立旧架构
