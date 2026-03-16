# 账号中心前后端分离重构设计

日期：2026-03-16

## 1. 目标

本设计用于指导项目第一阶段重构，目标如下：

- 建立新的图形化主入口，替代当前不可维护的临时 GUI。
- 将 UI 与业务逻辑解耦，形成前后端分离架构。
- 第一阶段先完成独立账号中心，不直接接入旧扫描与购买主流程。
- 为第二阶段平滑接入 legacy 查询、购买、调度逻辑预留稳定边界。

本设计明确采用以下终态方向：

- 前端：`PySide6`
- 后端：`FastAPI`
- 存储：`SQLite`
- 运行模式：本地桌面前后端分离

## 2. 范围与非目标

### 2.1 第一阶段范围

第一阶段仅实现“账号中心”，包括：

- 新建查询账号
- 编辑账号基础信息
- 保存与编辑 `API Key`
- 发起 Selenium 登录，补齐购买能力
- 展示查询能力状态
- 展示购买能力状态
- 展示购买池状态占位值
- 清除购买能力
- 删除账号

### 2.2 第一阶段非目标

第一阶段不包含以下内容：

- 不直接接入现有扫描主流程
- 不直接接入现有购买主流程
- 不复用旧 `account/*.json`
- 不要求与当前 CLI 共用账号存储
- 不实现 `API Key` 可用性校验
- 不支持手动粘贴 `cookie`

## 3. 核心约束

### 3.1 登录流程约束

购买能力只能通过 Selenium 登录生成，不能手动录入 `cookie`。

登录流程必须遵循以下交互规则：

1. 后端启动浏览器。
2. 用户手动扫码登录。
3. 浏览器自行抓取 `user_info` 与 `cookie`。
4. 即使已经抓到登录信息，也不能立即完成任务。
5. 必须等用户手动关闭浏览器后，任务才算完成。
6. 浏览器关闭后，后端再进行保存与状态更新。

### 3.2 账号能力约束

一个账号同时可以具有两类能力：

- 查询能力：主要由 `API Key` 决定
- 购买能力：主要由登录态和 `cookie` 决定

同一个账号可以先只有查询能力，后续再补购买能力。

### 3.3 状态建模约束

“购买能力”与“购买池状态”必须区分，不能混成一个状态。

根据现有 legacy 逻辑：

- 账号拥有有效登录态时，可以认为具备购买能力
- 账号因库存不足被移出购买池，不等于失去购买能力

### 3.4 新旧系统边界约束

第一阶段允许：

- 使用新的账号模型
- 使用新的账号存储
- 使用新的 GUI

第一阶段不要求：

- 新账号立即被当前 legacy 引擎直接消费
- 兼容旧账号 JSON 结构

## 4. 总体架构

采用“本地桌面前后端分离”架构。

### 4.1 架构分层

- 前端：`PySide6`
  - 负责页面展示
  - 收集输入
  - 发起接口调用
  - 展示任务状态

- 后端：`FastAPI`
  - 负责账号管理
  - 负责 Selenium 登录任务
  - 负责数据持久化
  - 后续负责 legacy 适配与流程编排

- 存储：`SQLite`
  - 负责新账号中心的数据持久化

### 4.2 职责边界

前端只做：

- 输入
- 轻量校验
- 触发后端操作
- 显示结果与状态

前端不做：

- 直接读写本地账号文件
- 直接调用 `autobuy.py`
- 自己维护登录与购买状态机

后端负责：

- 账号 CRUD
- Selenium 登录
- 冲突处理
- 购买能力清理
- 后续 legacy 适配

## 5. 目录设计

建议在现有项目中并行引入新架构，第一阶段不直接改旧主流程。

```text
app_frontend/
  main.py
  app/
    windows/
    widgets/
    dialogs/
    viewmodels/
    services/
    assets/

app_backend/
  main.py
  api/
    routes/
    schemas/
    websocket/
  application/
    use_cases/
    services/
  domain/
    models/
    enums/
  infrastructure/
    db/
    repositories/
    selenium/
    naming/
    proxy/
  workers/
    tasks/
    manager/
  shared/
    dto/
    errors/

data/
  app.db
```

说明：

- `app_frontend` 仅放 GUI 代码
- `app_backend` 仅放后端服务
- `data/app.db` 为第一阶段账号中心数据库
- 现有 `autobuy.py`、`c5_layered/` 暂时保留

## 6. 数据模型

第一阶段采用单表方案，避免过早抽象。

### 6.1 表：`accounts`

字段建议如下：

- `account_id` TEXT PRIMARY KEY
- `default_name` TEXT NOT NULL
- `remark_name` TEXT NULL
- `proxy_mode` TEXT NOT NULL
- `proxy_url` TEXT NULL
- `api_key` TEXT NULL
- `c5_user_id` TEXT NULL
- `c5_nick_name` TEXT NULL
- `cookie_raw` TEXT NULL
- `purchase_capability_state` TEXT NOT NULL
- `purchase_pool_state` TEXT NOT NULL
- `last_login_at` TEXT NULL
- `last_error` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
- `disabled` INTEGER NOT NULL DEFAULT 0

### 6.2 字段语义

- `account_id`
  - 本地主键
  - 所有前端操作都以它为准

- `default_name`
  - 系统自动生成默认名

- `remark_name`
  - 用户可修改备注名

- `proxy_mode`
  - `direct` 或 `custom`

- `proxy_url`
  - 自定义代理地址，可空

- `api_key`
  - 查询能力字段，可空

- `c5_user_id`
  - 购买能力绑定后的远端标识，可空

- `c5_nick_name`
  - 登录后获取的 C5 昵称，可空

- `cookie_raw`
  - 登录后获取的原始登录态，可空

### 6.3 状态值

`purchase_capability_state`：

- `unbound`
- `bound`
- `expired`

`purchase_pool_state`：

- 第一阶段固定使用 `not_connected`
- 第二阶段接 legacy 后扩展：
  - `available`
  - `paused_no_inventory`
  - `paused_not_login`

### 6.4 显示名规则

列表与详情页的显示名采用以下优先级：

1. `remark_name`
2. `c5_nick_name`
3. `default_name`

## 7. 前后端通信设计

第一阶段采用：

- 普通操作：HTTP
- 长任务状态：HTTP + WebSocket

这样做的原因：

- CRUD 操作保持简单
- Selenium 登录属于长任务，需要明确状态反馈
- WebSocket 只用于任务状态，不承接业务规则

## 8. 后端接口设计

### 8.1 账号接口

- `GET /accounts`
  - 获取账号列表

- `POST /accounts`
  - 创建新账号
  - 入参：
    - `remark_name`
    - `proxy_mode`
    - `proxy_url`
    - `api_key`

- `GET /accounts/{account_id}`
  - 获取账号详情

- `PATCH /accounts/{account_id}`
  - 编辑账号
  - 支持更新：
    - `remark_name`
    - `proxy_mode`
    - `proxy_url`
    - `api_key`

- `DELETE /accounts/{account_id}`
  - 删除账号

### 8.2 登录相关接口

- `POST /accounts/{account_id}/login`
  - 发起 Selenium 登录任务

- `POST /accounts/{account_id}/purchase-capability/clear`
  - 清除购买能力

- `POST /accounts/{account_id}/login/resolve`
  - 处理登录冲突
  - 支持动作：
    - `replace_with_new_account`
    - `create_new_account`
    - `cancel`

### 8.3 任务接口

- `GET /tasks/{task_id}`
  - 查询任务状态

- `GET /ws/tasks/{task_id}`
  - 推送任务状态

## 9. 代理策略设计

### 9.1 UI 输入规则

代理输入采用双模式：

- 默认完整地址输入框
- 同时支持拆分输入

兼容格式：

- `http://user:pass@host:port`
- `http://host:port`

留空代理视为直连。

### 9.2 登录代理策略

根据现有代码逻辑，Selenium 登录阶段必须保留以下代理行为：

- 优先使用浏览器代理认证插件处理带账号密码的代理
- 如果插件构建失败，再回退到普通 `--proxy-server`

该策略来自现有代码中为修复“代理连不上”问题所做的修改，不能在第一阶段被简化掉。

### 9.3 查询与 API 请求代理策略

后续第二阶段接入 legacy 查询与 API 请求时：

- 普通查询链路继续走 Python HTTP 客户端代理
- OpenAPI 链路继续走 Python HTTP 客户端代理
- 不应强行复用 Selenium 浏览器代理实现

## 10. UI 设计

### 10.1 主界面布局

采用工作台式账号中心：

- 左侧：账号列表
- 右侧：只读详情与操作区

### 10.2 左侧账号列表

左侧采用表格形式，字段如下：

- 显示名
- 查询能力
- 购买能力
- 购买池状态
- 代理

交互规则：

- 单击只负责选中
- 不自动切右侧详情
- 需要点击“查看详情”才切换详情

### 10.3 右侧详情区

右侧详情页默认只读，编辑必须通过弹窗进行。

区块如下：

- 基础信息
- 查询能力
- 购买能力
- 风险操作

#### 基础信息

第一阶段展示：

- 名称
- 备注名
- 代理

#### 查询能力

第一阶段展示：

- `API Key` 已设置 / 未设置
- 按钮：进入编辑弹窗

#### 购买能力

第一阶段同时展示两层状态：

- 购买能力状态：
  - 未绑定
  - 已绑定
  - 登录失效

- 购买池状态：
  - 第一阶段固定显示 `未接入`
  - 第二阶段接 legacy 后显示真实分配状态

并提供：

- `发起登录` 按钮

#### 风险操作

第一阶段建议保留以下动作：

- `清除购买能力`
- `删除账号`

### 10.4 新建账号弹窗

新建账号弹窗仅用于创建账号壳子与查询能力。

字段：

- `备注名`
- `代理模式`
- `代理输入`
- `API Key`

规则：

- 代理留空即视为直连
- `API Key` 只保存，不校验
- 创建成功后后端自动生成：
  - `account_id`
  - `default_name`

### 10.5 详情编辑弹窗

右侧详情页默认只读。

编辑动作统一进入弹窗，避免把主界面改成复杂表单。

### 10.6 登录任务弹窗

登录任务弹窗仅展示任务进度，不直接承接业务决策。

建议状态：

- 正在启动浏览器
- 等待扫码
- 已捕获登录信息
- 等待用户关闭浏览器
- 正在保存账号
- 登录完成
- 登录失败
- 用户取消
- 检测到账号冲突

说明：

- 登录代理默认使用当前账号保存的代理配置
- 如果要改代理，应先编辑账号，再重新发起登录

## 11. 登录冲突处理

当用户对某个已有账号发起登录，且登录结果中的 `c5_user_id` 与当前账号购买能力绑定信息不一致时，系统应提示冲突。

用户可选动作：

- 删除当前账号，并按本次登录结果新增一个新账号
- 保留当前账号，并按本次登录结果新增一个新账号
- 取消本次操作

重要说明：

- “覆盖当前账号”在实现语义上，不是直接覆写购买能力字段
- 而是“删除旧账号，再走新增账号流程”

如果选择新增新账号：

- 新账号视为完全独立账号
- 不继承旧账号备注
- 不继承旧账号代理
- 不继承旧账号 `API Key`

## 12. 第一阶段验收标准

第一阶段完成后，应满足：

1. 可以创建查询账号
2. 可以查看账号详情
3. 可以弹窗编辑备注、代理、`API Key`
4. 可以发起 Selenium 登录
5. 登录任务必须在“用户手动关闭浏览器后”才算完成
6. 可以保存购买能力到新数据库
7. 可以处理账号冲突
8. 可以清除购买能力
9. 可以删除账号
10. 整个账号中心不依赖旧 `account/*.json`

## 13. 第二阶段接入 legacy 的路线

第二阶段才开始接现有 legacy 查询与购买能力。

推荐顺序：

1. 新账号模型映射为 legacy 可运行账户对象
2. 接入 legacy 查询流程
3. 接入 legacy 购买流程
4. 接入 legacy 购买池状态
5. 最后再逐步清退 legacy 实现

原则：

- 新 GUI 不直接调用 `autobuy.py`
- 所有 legacy 逻辑都必须通过后端 adapter 接入

## 14. 风险与注意事项

### 14.1 风险

- Selenium 登录流程有人工参与，不适合按普通同步接口设计
- 代理策略若被简化，可能重新引入“代理连不上”的旧问题
- 第一阶段若提前接入旧扫描购买主流程，范围会失控

### 14.2 约束

- 第一阶段要先建立新边界，而不是直接拆 `autobuy.py`
- 旧引擎暂时保留，不应在第一阶段被大规模硬拆

## 15. 结论

本设计确认：

- 终态采用 `PySide6 + FastAPI + SQLite`
- 第一阶段先做独立账号中心
- 第一阶段不直接接入旧扫描购买主流程
- 购买能力与购买池状态必须分离建模与展示
- `userId` 不再作为本地主键，仅作为购买能力绑定后的远端标识
- 第二阶段通过 adapter 平滑接入 legacy 引擎
