# 账号 disabled 字段迁除设计

日期：2026-03-20

## 1. 目标

从新后端中移除账号级 `disabled` 字段，把查询与购买的能力控制语义完全收敛到以下两类真相源：

- 查询侧：
  - `new_api_enabled`
  - `fast_api_enabled`
  - `token_enabled`
- 购买侧：
  - `purchase_disabled`

本次设计的目标不是保留兼容过渡，而是在同一批实现中完成一次原子清理：

- 不再让查询侧依赖 `disabled`
- 不再让购买侧状态接口暴露 `disabled`
- 不再保留 `disabled -> purchase_disabled` 兼容映射
- 最终移除数据库中的 `accounts.disabled`

## 2. 当前问题

当前 `disabled` 已经和真实产品语义脱节，但仍残留在系统多个层面：

1. 查询容量统计会跳过 `disabled = true` 的账号。
2. 查询 runtime 的 worker 资格判断会直接拦掉 `disabled = true`。
3. 商品详情补全账号选择会跳过 `disabled = true`。
4. 购买 runtime 资格判断也还在看 `disabled`。
5. 账号中心的购买配置更新请求仍兼容旧字段：
   - 若传 `disabled`
   - 会被合并为 `purchase_disabled`
6. `AccountResponse` / `AccountCenterAccountResponse` 仍向前端返回 `disabled`。
7. 数据库 `accounts` 表仍保留 `disabled` 列。

这会导致两个问题：

- 代码层存在一套遗留“整号封停”心智
- 设计层已经冻结为“查询按单查询器控制，购买按 purchase_disabled 控制”

两者继续并存，只会持续制造歧义。

## 3. 已确认的用户决策

以下内容已经明确：

- 查询侧没有“整账号禁用”的产品需求
- 查询侧只支持单独禁用某个查询器
- 查询侧真相源是：
  - `new_api_enabled`
  - `fast_api_enabled`
  - `token_enabled`
- 购买侧禁用能力继续由 `purchase_disabled` 表达
- `disabled` 可以删除
- `disabled` 属于历史歧义，不需要保留兼容过渡
- 查询配置时应使用全部满足对应能力的账号：
  - token 查询使用全部有有效 token 的账号
  - API 查询使用全部有 `api_key` 且对应 mode 启用的账号
- 商品信息补全也应使用全部满足条件的账号，而不是受 `disabled` 影响
- 仓储/购买能力只以购买侧状态为准，不应与 `disabled` 混用

## 4. 方案比较

### 方案 A：直接删除字段与数据库列

优点：

- 改动直观
- 一次性删干净
- 彻底消除历史歧义
- 最符合当前真实产品语义

### 方案 B：兼容迁移后再删除

优点：

- 可以逐层移除引用
- 行为回归面可控
- 适合仍需兼容旧客户端的场景

缺点：

- 步骤更多
- 需要一次 schema 清理与 migration 收尾
- 会延长歧义字段在代码中的存活时间

### 方案 C：保留字段但完全废弃，不再使用

优点：

- 实现最省事

缺点：

- 永久保留歧义
- 后续开发仍会被旧字段误导
- 数据结构会继续背包袱

### 结论

采用方案 A。

原因：

- 魔尊已经明确确认它只是历史误写，不需要产品兼容期。
- 当前本地数据库中 `disabled=1` 也为 0。
- 因此最合适的做法是在一次原子改动中把所有真实引用一起删掉。

## 5. 目标语义

迁除完成后，账号能力模型冻结为：

### 5.1 查询侧

查询侧只认单查询器能力：

- `new_api_enabled`
- `fast_api_enabled`
- `token_enabled`

其余资格由已有条件决定，例如：

- 是否存在 `api_key`
- 是否存在有效 `NC5_accessToken`
- 是否出现 `Not login`

查询侧任何地方都不再参考 `disabled`。

### 5.2 购买侧

购买侧只认：

- `purchase_disabled`

及其既有状态字段：

- `purchase_capability_state`
- `purchase_pool_state`

购买侧任何地方都不再把 `disabled` 当成补充封停位。

## 6. 影响范围

本次迁除至少覆盖以下位置：

### 6.1 Domain / Repository / DB

- `app_backend/domain/models/account.py`
- `app_backend/application/use_cases/create_account.py`
- `app_backend/infrastructure/repositories/account_repository.py`
- `app_backend/infrastructure/db/models.py`
- `app_backend/infrastructure/db/base.py`
- 以及数据库 migration / 兼容清理逻辑

### 6.2 API Schemas

- `app_backend/api/schemas/accounts.py`
- `app_backend/api/schemas/account_center.py`

### 6.3 Query Runtime / Services

- `app_backend/application/services/query_mode_capacity_service.py`
- `app_backend/infrastructure/query/runtime/mode_runner.py`
- `app_backend/infrastructure/query/collectors/detail_account_selector.py`

### 6.4 Purchase Runtime

- `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py`

其中除了 eligibility 判断，还必须清理账号行快照中的遗留 `disabled` 输出。

### 6.5 Frontend / Tests

- `app_desktop_web` 中与账号夹具、请求体、断言有关的测试

## 7. 原子删除设计

本次不做分阶段兼容迁移。

实现策略冻结为：

- 在同一批代码改动中同时删除：
  - 运行逻辑引用
  - 对外 schema 字段
  - legacy 请求兼容
  - domain / repository 映射
  - 数据库列

允许分多个 implementation chunk 落地与验证，但这些 chunk 共同组成一次语义原子切换：

- 合并后，系统中不再存在 `disabled` 的产品语义
- 不保留“先留字段再慢慢迁”的过渡期

### 7.1 运行逻辑删除

#### 查询容量统计

`QueryModeCapacityService` 不再因为 `account.disabled` 跳过账号，而只依据：

- mode 开关
- `api_key`
- `token/cookie`
- `Not login`

#### 查询 runtime 资格

`ModeRunner._is_eligible_account()` 不再检查 `account.disabled`。

#### 商品详情补全

`DetailAccountSelector` 不再检查 `account.disabled`，只要求账号具备有效 token。

#### 购买 runtime 资格

`PurchaseRuntimeService._is_eligible_account()` 不再检查 `account.disabled`，只依据：

- `purchase_capability_state`
- `purchase_pool_state`
- `purchase_disabled`
- 现有库存/登录状态

### 7.2 接口与兼容删除

#### Account schemas

从以下 response 中移除 `disabled`：

- `AccountResponse`
- `AccountCenterAccountResponse`

#### 购买配置兼容映射

删除 `AccountPurchaseConfigUpdateRequest` 中的：

- `disabled`
- `merge_legacy_disabled_field()`

之后购买配置接口只接受：

- `purchase_disabled`
- `selected_steam_id`

不再接受旧的 `disabled` 兼容写法。

旧客户端若继续提交 `disabled`，失败语义必须冻结为显式拒绝，而不是静默忽略。

推荐 contract：

- `AccountPurchaseConfigUpdateRequest` 开启严格字段校验
- 未知字段直接返回 `422`
- 因此旧请求体中的 `disabled` 会被明确拒绝

不允许迁移后出现：

- 接口返回成功
- 但 `purchase_disabled` 没变
- 旧字段被框架静默吞掉

### 7.3 Domain / Repository / DB 删除

#### Domain model

从 `Account` 中移除：

- `disabled`

并同步清理：

- `CreateAccountUseCase` 中的 `Account(disabled=False)` 构造参数

#### Repository

删除 create / to_domain / update 路径中对 `disabled` 的映射。

同时确保删除后：

- 新账号创建不再写入 `disabled`
- 仓储回填 domain model 时不再依赖该列

#### DB

对 `accounts.disabled` 做 migration 清理。

本项目使用 SQLite，因此迁移策略冻结为：

- 若当前 migration 体系支持安全 drop column，则直接 drop
- 若不支持，则采用重建表方案：
  - 新建不含 `disabled` 的临时表
  - 拷贝数据
  - 替换旧表

不允许只在 ORM 层假装删除而数据库继续保留该列。

## 8. 风险与边界

### 8.1 当前数据状态

本地现有数据库中：

- `data/app.db`
- `data/login_verify_20260319_002118.db`

账号记录的 `disabled` 当前均为 `0`。

这说明当前数据面没有“真实使用中的 disabled 账号”。

因此本次风险主要来自代码引用，而不是历史数据迁移。

仍然需要注意以下边界：

- 测试夹具仍可能构造 `disabled=true`
- 某些旧客户端仍可能提交 `disabled`
- 某些状态文案仍可能把它当成显示字段

这些都要在同一批改动中一起清理，而不是因此保留兼容期。

## 9. 非目标

本次明确不做：

- 不新增“整账号查询禁用”替代字段
- 不改 `purchase_disabled` 的购买侧语义
- 不改变 `new_api_enabled / fast_api_enabled / token_enabled` 的接口形态
- 不顺手重构账号中心全部 schema
- 不扩大到登录任务系统

## 10. 测试重点

后续实现至少需要覆盖：

1. `new_api_enabled=false` 时，只影响 `new_api` 容量与运行资格。
2. `fast_api_enabled=false` 时，只影响 `fast_api` 容量与运行资格。
3. `token_enabled=false` 时，只影响 `token` 容量与运行资格。
4. `purchase_disabled=true` 不影响查询侧 worker 可用性。
5. 查询容量统计不再依赖 `disabled`。
6. 查询 runtime 资格判断不再依赖 `disabled`。
7. 商品详情补全账号选择不再依赖 `disabled`。
8. 购买 runtime 资格判断不再依赖 `disabled`。
9. 购买 runtime 账号快照不再输出 `disabled`。
10. `AccountResponse` 不再返回 `disabled`。
11. `AccountCenterAccountResponse` 不再返回 `disabled`。
12. 购买配置接口若继续收到旧 `disabled` 字段，明确返回 `422`。
13. 仓储 create / read / update 在移除 `disabled` 后仍能正常读写账号。
14. 新账号创建在删除 `disabled` 后仍能正常构造与落库。
15. 数据库 migration 后，`accounts` 表中不再存在 `disabled` 列。

## 11. 实施顺序建议

虽然语义上是一次原子删除，但实现上仍建议按 3 个 chunk 执行并连续合入：

### Chunk 1：运行逻辑与 schema 清理

- Query capacity
- Query runtime
- Detail selector
- Purchase runtime eligibility
- Account schemas
- Purchase runtime account snapshot cleanup

### Chunk 2：请求兼容、domain 与 repository 清理

- 删除 legacy `disabled` 请求兼容
- Domain model
- Create account use case
- Repository
- Frontend fixtures / renderer tests

### Chunk 3：数据库列删除与最终验证

- DB schema migration
- 数据回读验证
- 全链路回归验证

## 12. 结论

`disabled` 现在已经不再代表真实产品语义，但它仍然活在：

- 运行逻辑
- 对外 schema
- 仓储映射
- 数据库列

因此它不是“需要慢慢迁”，而是“应该一次删干净”。

正确做法是：

- 以一次原子语义切换为目标
- 在同一批实现中删掉所有真实引用
- 不保留历史兼容口

只有这样，才能把“单查询器控制 + purchase_disabled”这套新语义真正收干净，而不是继续背着一个由历史误写产生的伪能力字段。
