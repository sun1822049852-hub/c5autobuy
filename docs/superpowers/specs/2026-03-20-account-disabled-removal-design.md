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

本次设计的目标不是“把列删掉”这么简单，而是安全完成一次语义迁移：

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
- 但不能直接硬删，必须分阶段迁除

## 4. 方案比较

### 方案 A：直接删除字段与数据库列

优点：

- 改动直观
- 一次性删干净

缺点：

- 会同时打断：
  - 查询容量统计
  - 查询 runtime 资格判断
  - 商品详情补全
  - API schema
  - 仓储与数据库映射
- 风险过高

### 方案 B：兼容迁移后再删除

优点：

- 可以逐层移除引用
- 行为回归面可控
- 更适合已有脏历史字段的退场

缺点：

- 步骤更多
- 需要一次 schema 清理与 migration 收尾

### 方案 C：保留字段但完全废弃，不再使用

优点：

- 实现最省事

缺点：

- 永久保留歧义
- 后续开发仍会被旧字段误导
- 数据结构会继续背包袱

### 结论

采用方案 B。

原因：

- 这是唯一能同时满足“删掉遗留语义”和“避免运行时回归”的方案。

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

## 7. 分阶段迁除设计

### 7.1 第一阶段：先移除运行逻辑依赖

先把所有运行逻辑里的 `disabled` 判断迁走，但暂时保留字段本身。

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

第一阶段完成后，`disabled` 仍存在，但已经不再参与实际运行决策。

### 7.2 第二阶段：移除 API 兼容语义

当运行逻辑完全不再依赖后，再清理接口层。

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

### 7.3 第三阶段：移除 domain / repository / DB 字段

当 API 层不再暴露后，再做实体与数据库收尾。

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

## 8. 数据兼容与风险控制

### 8.1 当前数据状态

本地现有数据库中：

- `data/app.db`
- `data/login_verify_20260319_002118.db`

账号记录的 `disabled` 当前均为 `0`。

这说明：

- 当前数据面没有“真实使用中的 disabled 账号”
- 删除字段的主要风险在代码兼容，而不在历史数据语义丢失

### 8.2 风险边界

虽然当前数据中 `disabled=1` 为 0，但不能据此跳过分阶段迁移。

必须假定以下风险仍然存在：

- 测试夹具仍可能构造 `disabled=true`
- 某些旧客户端仍可能提交 `disabled`
- 某些状态文案仍可能把它当成显示字段

因此顺序必须保持：

1. 移除运行依赖
2. 移除 API 兼容
3. 移除 DB 列

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

建议按 3 个 chunk 执行：

### Chunk 1：运行逻辑去依赖

- Query capacity
- Query runtime
- Detail selector
- Purchase runtime eligibility

### Chunk 2：接口与测试清理

- Schemas
- Legacy request compatibility
- Purchase runtime account snapshot cleanup
- Frontend fixtures / renderer tests

### Chunk 3：实体与数据库迁除

- Domain model
- Create account use case
- Repository
- DB schema migration

## 12. 结论

`disabled` 现在已经不再代表真实产品语义，但它仍然活在：

- 运行逻辑
- 对外 schema
- 仓储映射
- 数据库列

因此它不是“不能删”，而是“不能直接删”。

正确做法是：

- 先去掉运行依赖
- 再去掉 API 兼容
- 最后删实体与数据库列

只有这样，才能把“单查询器控制 + purchase_disabled”这套新语义真正收干净，而不是再留一个会继续误导后续开发的遗留开关。
