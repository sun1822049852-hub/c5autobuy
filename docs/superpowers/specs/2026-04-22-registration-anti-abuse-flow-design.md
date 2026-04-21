# 注册三步流与防批量刷邮箱设计

## 目标

把当前“一屏输入邮箱、验证码、账号名、密码”的注册交互，收口为真正的三步注册流，并把批量刷注册的第一道拦截点前移到“邮箱发码”阶段。

本轮设计只解决两件事：

- 前端注册交互必须拆成清晰的三步状态机。
- 后端必须把邮箱风控、验证码验证与最终注册拆成独立职责，而不是继续把所有校验压在最终注册接口里。

## 不改项

- 不改现有登录、找回密码的总体入口结构。
- 不新增图形验证码、短信验证码、人工审核等额外注册步骤。
- 不改“本地程序只做代理，远端统一鉴权”的总体架构。
- 不在本地桌面端持久化新的会员或多租户数据隔离逻辑。

## 现状

- 当前程序账号注册页仍是一屏式表单，邮箱、验证码、账号名、密码同时出现，注册流程层次不清。
- 当前本地后端只暴露“发注册验证码”和“完成注册”两段接口，缺少独立的“验证验证码”阶段。
- 当前发验证码前缺少明确的前端状态门槛和后端风控阶段，批量刷邮箱时拦截点过晚。

## 设计决策

### 1. 总体流程改为三步三接口

注册链路固定为以下顺序：

1. 邮箱输入页
2. 验证码页
3. 设置账号名与密码页

对应后端接口固定为：

1. `POST /program-auth/register/send-code`
2. `POST /program-auth/register/verify-code`
3. `POST /program-auth/register/complete`

不再采用“前端拆三步、后端仍只保留两接口”的假分步方案。

### 2. 风控前移到发码阶段

前端在邮箱输入页只做本地格式校验与按钮禁用，真正的风控判断全部放在远端统一鉴权侧的发码接口完成。

发码阶段至少承担以下职责：

- 服务端再次校验邮箱格式。
- 标准化邮箱内容（去空格、转小写）。
- 检查临时邮箱 / 一次性邮箱域名。
- 检查高频请求（邮箱、IP、设备、安装实例）。
- 按风险等级决定是否允许发码或直接拒绝；冷却期内统一返回 `REGISTER_SEND_RETRY_LATER`，不采用“排队后延迟发送”的隐式状态。

### 3. 验证码通过后签发一次性注册票据

验证码验证成功后，后端签发短时、一次性 `verification_ticket`。

第三步“完成注册”必须依赖这张票据；没有票据、票据过期、票据已使用或上下文不匹配时，后端一律拒绝创建账号。

### 4. 用户可见错误保持模糊

为了避免被批量探测，注册链路里的邮箱相关失败提示默认保持模糊，不向用户明确暴露以下内部原因：

- 命中临时邮箱黑名单
- 请求过频
- 邮箱已注册
- 风控评分过高

用户可见口径统一收口为“无法继续注册，请稍后重试或直接登录/找回密码”这一类通用提示。只有账号名重复、密码强度不足这类第三步本地字段问题可以明确提示。

## 关键常量与会话规则

首发默认常量固定如下，后续可做远端配置化，但实现与测试先按以下值落地：

- 验证码长度：`6` 位数字
- 单次验证码有效期：`600` 秒
- 单个注册会话有效期：`1800` 秒
- 单会话验证码最大校验次数：`5`
- 单会话最大发码次数：`5`
- 重新发送冷却时间：`60` 秒
- `verification_ticket` 有效期：`900` 秒

首发限流窗口固定如下：

- 同邮箱：`60` 秒内最多 `1` 次发码，`24` 小时内最多 `5` 次
- 同 `install_id`：`10` 分钟内最多 `3` 次发码，`24` 小时内最多 `20` 次
- 同 `device_fingerprint`（若有）：`10` 分钟内最多 `3` 次发码，`24` 小时内最多 `20` 次
- 同源 IP：`10` 分钟内最多 `10` 次发码，`24` 小时内最多 `50` 次

注册会话规则固定如下：

- 第一次 `send-code` 成功时生成 `register_session_id`。
- 在同一邮箱、同一 `install_id` 且会话未过期的前提下，重新发送验证码时继续复用同一个 `register_session_id`。
- 每次重新发送都会生成新验证码，并立即作废上一个未使用验证码。
- 重新发送不会刷新 `register_session_id`，只会更新验证码哈希、过期时间、发送次数与冷却时间。
- 会话达到最大发码次数、超过会话有效期、邮箱被修改或验证码校验成功后，当前待验证会话即失效。
- 对同一邮箱、同一 `install_id` 的重复点击发码请求，远端应在 `2` 秒短幂等窗口内只发送一次邮件：首个请求负责真正发码，其余并发请求复用同一 `register_session_id` 与当前冷却时间，不额外增加发送次数。幂等 key 固定为 `normalized_email + install_id + register_session_id_or_empty`。
- 对同一会话的重复验码请求，只有第一个成功请求能将会话推进到“已验证”；其余并发或迟到请求统一返回 `REGISTER_SESSION_INVALID`，不再重复签发票据。

`verification_ticket` 规则固定如下：

- 票据采用后端生成的高熵不透明随机串，不使用前端可自解的 JWT。
- 票据与 `normalized_email + register_session_id + install_id` 绑定；若当前链路已有 `device_fingerprint`，可一并绑定。
- 票据不强绑 IP，避免移动网络切换导致误伤。
- 票据只能成功消费一次；并发提交时必须由后端原子消费，只有第一个成功请求能完成注册，其余请求统一返回票据失效。

## 错误码与前端映射

注册链路对前端返回机器可分支的 `error_code`，但用户可见文案保持分桶模糊。

### 用户可见文案分桶

- 邮箱页：
  - `REGISTER_INPUT_INVALID`
  - `REGISTER_SEND_RETRY_LATER`
  - `REGISTER_SEND_DENIED`
  - `REGISTER_SERVICE_UNAVAILABLE`
- `REGISTER_INPUT_INVALID` 显示：`请输入有效邮箱地址`
  - 其余统一显示：`无法继续注册，请稍后重试`
- 验证码页：
  - `REGISTER_CODE_INVALID_OR_EXPIRED`
  - `REGISTER_CODE_ATTEMPTS_EXCEEDED`
  - `REGISTER_SESSION_EMAIL_MISMATCH`
  - `REGISTER_SESSION_INVALID`
  - `REGISTER_SERVICE_UNAVAILABLE`
  - 统一显示：`验证码错误或已失效，请重新获取`
- 设置账号页：
  - `REGISTER_TICKET_INVALID_OR_EXPIRED`：显示 `注册已失效，请重新验证邮箱`，并强制退回第二步
  - `REGISTER_USERNAME_TAKEN`：显示 `账号名已被使用`
  - `REGISTER_USERNAME_INVALID`：显示账号名规则提示
  - `REGISTER_PASSWORD_WEAK`：显示密码规则提示
  - `REGISTER_EMAIL_UNAVAILABLE`：显示 `当前邮箱无法继续注册，请直接登录或找回密码`

### 错误码边界

- 前端只能基于 `error_code` 控制流程跳转、倒计时和输入框错误态。
- 前端不得基于任意后端自由文本做流程判断。
- 后端返回的 `message` 只作为日志辅助，不作为产品逻辑判断依据。

### 通用失败响应包络

三接口失败时统一返回以下 JSON 结构：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ok` | `false` | 是 | 固定为失败 |
| `error_code` | `string` | 是 | 前端唯一流程分支依据 |
| `message` | `string` | 是 | 日志辅助文本，不参与流程判断 |
| `request_id` | `string` | 是 | 便于排查链路 |
| `retry_after_seconds` | `number \\| null` | 否 | 仅在限流或冷却场景返回 |

倒计时字段优先级固定如下：

1. 若失败响应 JSON 中存在 `retry_after_seconds`，以前者为准。
2. 否则若 HTTP Header 中存在 `Retry-After`，使用其秒数。
3. 若两者都不存在，则前端沿用当前倒计时，不自行重置为新的默认值。

`resend_after_seconds` 只用于成功发码后的初始冷却展示；`retry_after_seconds` 只用于失败限流后的继续冷却，两者不得混用。

### `error_code` 到前端状态动作总表

| `error_code` | 当前步骤 | 前端动作 |
|---|---|---|
| `REGISTER_INPUT_INVALID` | 第一步 | 停留当前页，标红邮箱输入框 |
| `REGISTER_SEND_RETRY_LATER` | 第一步/第二步 | 停留当前页，按钮禁用，按冷却优先级继续倒计时 |
| `REGISTER_SEND_DENIED` | 第一步/第二步 | 停留当前页，显示通用失败文案 |
| `REGISTER_CODE_INVALID_OR_EXPIRED` | 第二步 | 停留当前页，清空验证码输入框 |
| `REGISTER_SESSION_EMAIL_MISMATCH` | 第二步 | 停留当前页，清空验证码输入框，并切为重新获取验证码态 |
| `REGISTER_SESSION_INVALID` | 第二步 | 停留当前页，切为重新获取验证码态 |
| `REGISTER_CODE_ATTEMPTS_EXCEEDED` | 第二步 | 停留当前页，切为重新获取验证码态 |
| `REGISTER_TICKET_INVALID_OR_EXPIRED` | 第三步 | 退回第二步，清空账号名/密码输入 |
| `REGISTER_USERNAME_INVALID` | 第三步 | 停留当前页，标红账号名输入框 |
| `REGISTER_USERNAME_TAKEN` | 第三步 | 停留当前页，提示账号名已占用 |
| `REGISTER_PASSWORD_WEAK` | 第三步 | 停留当前页，标红密码输入框 |
| `REGISTER_EMAIL_UNAVAILABLE` | 第三步 | 停留当前页，提示转登录/找回密码 |
| `REGISTER_SERVICE_UNAVAILABLE` | 任意步骤 | 停留当前页，不自动重试 |

### 注册状态迁移表

| 当前状态 | 触发条件 | 下一状态 | 需要清空的本地字段 |
|---|---|---|---|
| `register_email` | `send-code` 成功 | `register_code` | 清空 `verification_ticket` |
| `register_email` | `REGISTER_INPUT_INVALID / REGISTER_SEND_* / REGISTER_SERVICE_UNAVAILABLE` | `register_email` | 不清空已输入邮箱 |
| `register_code` | `verify-code` 成功 | `register_credentials` | 保留 `register_session_id`，写入 `verification_ticket` |
| `register_code` | `REGISTER_CODE_INVALID_OR_EXPIRED` | `register_code` | 清空验证码输入框 |
| `register_code` | `REGISTER_SESSION_INVALID / REGISTER_CODE_ATTEMPTS_EXCEEDED / REGISTER_SESSION_EMAIL_MISMATCH` | `register_code` | 清空验证码输入框，清空 `verification_ticket` |
| `register_code` | 点击 `修改邮箱` | `register_email` | 清空验证码输入框、`register_session_id`、`verification_ticket`、倒计时 |
| `register_credentials` | `complete` 成功 | `register_success` | 清空验证码输入框 |
| `register_credentials` | `REGISTER_TICKET_INVALID_OR_EXPIRED` | `register_code` | 清空账号名、密码、`verification_ticket` |
| `register_credentials` | `REGISTER_USERNAME_* / REGISTER_PASSWORD_WEAK / REGISTER_EMAIL_UNAVAILABLE / REGISTER_SERVICE_UNAVAILABLE` | `register_credentials` | 不清空邮箱与 `register_session_id` |

## 前端交互设计

### A. 第一步：邮箱输入页

页面元素仅保留：

- 邮箱输入框
- `下一步` 按钮
- 返回登录 / 找回密码入口

交互规则：

- 输入时做本地正则校验。
- 邮箱格式非法时，`下一步` 按钮保持禁用。
- 只有本地校验通过后，点击 `下一步` 才会调用 `send-code`。
- `send-code` 请求中要附带本地已有的安装实例标识与必要环境信息，供后端风控使用。
- 发码成功后自动跳到第二步。
- 发码失败时停留在当前页，只显示模糊错误，不显示具体风控命中原因。
- 脱敏邮箱规则固定为：域名部分完整保留；邮箱名前缀长度为 `1` 或 `2` 时统一显示为 `首字符 + *`，长度大于等于 `3` 时显示为 `首字符 + *** + 末字符`。例如：`a@x.com -> a*@x.com`、`ab@x.com -> a*@x.com`、`alice@qq.com -> a***e@qq.com`。

### B. 第二步：验证码页

页面元素：

- 验证码输入框
- 脱敏邮箱展示
- `重新发送验证码` 按钮
- `修改邮箱` 入口

交互规则：

- 从第一步发码成功后自动进入本页。
- 验证码输入框默认自动聚焦。
- 输入满设定位数后可自动触发校验，也允许保留 `验证` 按钮作为显式提交。
- `重新发送验证码` 必须受后端返回的 `resend_after_seconds` 控制，前端本地倒计时只负责展示，不自定义冷却值。
- 第二步点击 `重新发送验证码` 实际仍调用 `send-code`；若返回 `REGISTER_SEND_RETRY_LATER`，页面停留在第二步，继续展示当前脱敏邮箱，并使用失败响应中的 `retry_after_seconds` 或 HTTP `Retry-After` 继续倒计时。
- 第二步重发若返回 `REGISTER_SEND_DENIED` 或 `REGISTER_SERVICE_UNAVAILABLE`，页面仍停留第二步，只显示邮箱相关通用失败文案，不回退第一步。
- 点击 `修改邮箱` 时返回第一步，并清空当前验证码态。
- 验证通过后自动进入第三步，并保存后端返回的 `verification_ticket`。
- 验证失败、过期、尝试过多时，只显示通用失败提示；当 `error_code=REGISTER_CODE_ATTEMPTS_EXCEEDED` 或 `REGISTER_SESSION_INVALID` 时，页面直接切到“请重新获取验证码”的状态。

### C. 第三步：设置账号与密码页

页面元素：

- 已验证邮箱展示
- 账号名输入框
- 密码输入框
- `完成注册` 按钮

交互规则：

- 只有第二步验证通过后才允许进入本页。
- 本页不再展示邮箱输入框，也不允许绕过验证码直接提交账号名和密码。
- 提交时必须携带 `verification_ticket`。
- 若后端返回 `REGISTER_TICKET_INVALID_OR_EXPIRED`，前端必须强制退回第二步重新验码。
- 注册成功后固定行为为：本地后端立即写入程序账号登录态，前端关闭注册弹窗并回到左侧程序账号状态卡的“已登录”展示，不再停留在注册页。

## 前端状态机

注册弹窗状态固定为：

- `register_email`
- `register_code`
- `register_credentials`
- `register_submitting`
- `register_success`

关键边界：

- `register_code` 只能由 `send-code` 成功进入。
- `register_credentials` 只能由 `verify-code` 成功进入。
- `register_success` 只能由 `complete` 成功进入。
- 任一阶段刷新、退出或关闭弹窗后，未完成的注册状态应清空，避免复用过期票据。

## 后端接口设计

### 1. `POST /program-auth/register/send-code`

职责：

- 接收邮箱并执行风控。
- 风控通过后创建待验证会话并发送邮件验证码。

请求体契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `email` | `string` | 是 | 用户输入邮箱，后端会标准化 |
| `install_id` | `string` | 是 | 本地安装实例稳定标识 |
| `register_session_id` | `string \\| null` | 否 | 第一次发码可为空；第二步重发时必须带上当前会话 ID |
| `device_fingerprint` | `string \\| null` | 否 | 仅在当前程序已存在稳定设备哈希时透传，不额外新增硬件采集 |
| `client_version` | `string` | 是 | 当前桌面程序版本 |

成功响应契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ok` | `true` | 是 | 固定为成功 |
| `register_session_id` | `string` | 是 | 当前待验证会话 ID |
| `masked_email` | `string` | 是 | 按固定脱敏规则返回 |
| `code_length` | `number` | 是 | 首发固定 `6` |
| `code_expires_in_seconds` | `number` | 是 | 首发固定 `600` |
| `resend_after_seconds` | `number` | 是 | 首发固定 `60`，以后端返回为准 |

失败响应契约：

| HTTP | `error_code` | 前端动作 |
|---|---|---|
| `400` | `REGISTER_INPUT_INVALID` | 停留邮箱页，提示邮箱格式不正确 |
| `429` | `REGISTER_SEND_RETRY_LATER` | 停留当前页，并以 `retry_after_seconds` 或 HTTP `Retry-After` 更新倒计时 |
| `403` | `REGISTER_SEND_DENIED` | 停留邮箱页，提示无法继续注册 |
| `503` | `REGISTER_SERVICE_UNAVAILABLE` | 停留邮箱页，提示稍后重试 |

校验要点：

- 服务端再次做邮箱格式校验，不信任前端正则结果。
- 标准化邮箱后再参与限流与存储。
- 检查域名黑名单、临时邮箱、异常域名。
- MX / 基础投递能力检查只作为低优先级增强项，首发不阻塞主链实现；若接入，必须保证超时快速失败且不得拖慢发码主路径。
- 按邮箱、IP、安装实例、设备标识分别限流。
- 若邮箱已注册或被风控拒绝，统一返回 `REGISTER_SEND_DENIED`，不发验证码，也不在第一步或第二步向用户暴露“邮箱已存在”这一具体原因。
- 对可疑流量返回模糊失败结果，不回传风控细节。
- 验证码只保存哈希，不保存明文。

### 2. `POST /program-auth/register/verify-code`

职责：

- 校验验证码是否匹配当前待验证会话。
- 校验成功后签发一次性 `verification_ticket`。

请求体契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `email` | `string` | 是 | 与第一步输入一致，用于前后端对账 |
| `code` | `string` | 是 | 固定为 `6` 位数字字符串 |
| `register_session_id` | `string` | 是 | 来自 `send-code` |
| `install_id` | `string` | 是 | 与第一步保持一致 |

成功响应契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ok` | `true` | 是 | 固定为成功 |
| `verification_ticket` | `string` | 是 | 一次性注册票据 |
| `ticket_expires_in_seconds` | `number` | 是 | 首发固定 `900` |

失败响应契约：

| HTTP | `error_code` | 前端动作 |
|---|---|---|
| `400` | `REGISTER_CODE_INVALID_OR_EXPIRED` | 停留验证码页，提示重新获取 |
| `409` | `REGISTER_SESSION_EMAIL_MISMATCH` | 停留验证码页并清空当前验证码输入，提示重新获取 |
| `410` | `REGISTER_SESSION_INVALID` | 停留验证码页，切为重新发码态 |
| `429` | `REGISTER_CODE_ATTEMPTS_EXCEEDED` | 停留验证码页，切为重新发码态 |
| `503` | `REGISTER_SERVICE_UNAVAILABLE` | 停留验证码页，提示稍后重试 |

校验要点：

- 校验验证码是否匹配、是否过期、是否已使用。
- 若 `email` 与 `register_session_id` 绑定邮箱不一致，直接拒绝并返回 `409 REGISTER_SESSION_EMAIL_MISMATCH`，不得继续尝试验码。
- 限制单个会话的最大尝试次数。
- 超过尝试上限后使当前验证码失效，并要求重新发码。
- 成功后立即把验证码状态标记为“已验证，不可重复使用”。
- `verification_ticket` 绑定邮箱与本次注册会话，只允许短时间内使用一次。

### 3. `POST /program-auth/register/complete`

职责：

- 校验 `verification_ticket`。
- 校验账号名和密码。
- 在事务内创建账号并作废票据。

请求体契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `email` | `string` | 是 | 当前已验证邮箱 |
| `username` | `string` | 是 | 用户自定义账号名 |
| `password` | `string` | 是 | 明文密码，仅经 HTTPS 传输 |
| `verification_ticket` | `string` | 是 | 来自 `verify-code` |
| `install_id` | `string` | 是 | 与前两步保持一致 |

成功响应契约：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ok` | `true` | 是 | 固定为成功 |
| `account_summary` | `object` | 是 | 最小账号摘要，至少包含 `email`、`username` |
| `auth_session` | `object` | 是 | 复用现有登录成功后的远端认证结构：`refresh_token + access_bundle(snapshot/signature/kid) + user` |

失败响应契约：

| HTTP | `error_code` | 前端动作 |
|---|---|---|
| `400` | `REGISTER_USERNAME_INVALID` | 停留第三步，标红账号名输入框 |
| `400` | `REGISTER_PASSWORD_WEAK` | 停留第三步，标红密码输入框 |
| `409` | `REGISTER_USERNAME_TAKEN` | 停留第三步，提示账号名已占用 |
| `409` | `REGISTER_EMAIL_UNAVAILABLE` | 停留第三步，提示转登录/找回密码 |
| `410` | `REGISTER_TICKET_INVALID_OR_EXPIRED` | 强制退回第二步 |
| `503` | `REGISTER_SERVICE_UNAVAILABLE` | 停留第三步，提示稍后重试 |

校验要点：

- `verification_ticket` 必须存在、未过期、未使用、与邮箱匹配。
- 账号名要检查规则与唯一性。
- 密码要检查最小强度要求：长度 `8-64`，至少同时包含字母与数字。
- 创建账号成功后立刻作废票据，防止重放。
- 若邮箱已被其他流程抢先注册，也只返回通用失败或引导转登录/找回密码，不暴露更多内部状态。
- `REGISTER_EMAIL_UNAVAILABLE` 只允许出现在第三步，用于表示邮箱在验证码通过后到最终创建前被其他流程占用；第一步和第二步不得提前暴露该状态。

## 后端会话与数据约束

后端至少需要两类短时状态：

### 注册待验证会话

用于承载：

- 标准化邮箱
- 验证码哈希
- 过期时间
- 发送次数
- 尝试次数
- 首次请求 IP / 设备 / 安装实例摘要
- 风控结果摘要

补充约束：

- 该会话只保留短期防刷与验码所需字段，不写入正式账号资料。
- 服务器侧记录请求来源 IP；前端只透传 `install_id`、`client_version` 和已有稳定设备哈希，不新增原始硬件指纹采集。

### 验证通过票据

用于承载：

- 关联邮箱
- 关联注册会话
- 签发时间
- 过期时间
- 是否已使用

这两类状态都属于短期凭据，不进入本地共享业务数据，不参与本地多租户切换。

## 安全与风控要求

- 风控主判断发生在远端统一鉴权，不在本地桌面端落复杂策略。
- 对同邮箱、同 IP、同设备、同安装实例做分层限流，避免单点绕过。
- 用户可见文案默认不暴露精确失败原因，降低账号探测与风控探测价值。
- 对中高风险请求，可采用更长冷却时间、静默拒绝或后续再接图形挑战；但本轮不把挑战升级做成必选流程。
- `password`、`code`、`register_session_id`、`verification_ticket` 都视为敏感凭据；前端、本地后端、远端控制面日志不得明文记录这些字段。

## 兼容与发布顺序

本轮涉及三段职责，范围边界固定如下：

- 本仓负责：前端三步注册交互、本地后端三接口转发、错误码映射与状态切换。
- 远端控制面负责：发码风控、验证码会话、`verification_ticket`、最终账号创建。

能力开关与回退策略固定如下：

- 本地后端对前端额外暴露 `registration_flow_version` 能力字段，取值只有 `2` 或 `3`。
- 默认值为 `2`，继续使用旧的两接口注册页。
- 仅当远端控制面三接口全部可用时，才把该值切到 `3`。探测目标固定为：
  - `POST /api/auth/register/send-code`
  - `POST /api/auth/register/verify-code`
  - `POST /api/auth/register/complete`
- 前端只在 `registration_flow_version=3` 时启用本次三步注册 UI；否则继续保留旧链路，避免桌面端先发而远端未就绪。

发布顺序固定为：

1. 远端控制面先上线 `send-code / verify-code / complete` 三接口，并暂时保留旧的两接口兼容能力。
2. 本仓前端与本地后端切到新三步流。
3. 确认线上桌面端已全部升级后，再考虑下线旧的两接口注册路径。

在第 1 步完成前，前端不得强切到新三步流，否则会出现本地已切 UI、远端接口未就绪的阻塞。

## 集成影响

### 前端

- 当前注册表单需要从“一屏式”改成真正的三步状态机。
- 现有发注册验证码动作保留，但要挂到第一步。
- 需要新增“验证验证码”动作与状态。
- 最终注册动作改为依赖 `verification_ticket`。
- 三步 UI 是否启用受本地后端返回的 `registration_flow_version` 控制。
- 前端测试必须锁定以下边界：`code_length=6`、`resend_after_seconds` 以后端响应为准、`masked_email` 按固定规则展示。

### 本地后端

- 当前本地转发层需要补出 `verify-code` 路由与对应 application/gateway 调用。
- 本地后端不承载最终风控决策，只负责透传必要上下文并回传通用结果。
- 本地后端与前端都不得记录包含明文 `password` 的请求体日志；若现有日志中间件会记录表单载荷，必须在 `complete` 路径对密码字段做脱敏或跳过记录。
- 本地后端继续复用现有 `/program-auth/*` 路由组与 `RemoteControlPlaneClient` 转发模式，不新增额外签名链；注册三接口仍走当前 `controlPlaneBaseUrl + /api/auth/*` 远端网关。
- 注册相关三接口属于匿名入口，不复用 `refresh_token` 登录态；唯一新增的跨步骤上下文字段是 `install_id`、`register_session_id`、`verification_ticket`。
- 远端路径映射固定为：
  - 本地 `POST /program-auth/register/send-code` -> 远端 `POST /api/auth/register/send-code`
  - 本地 `POST /program-auth/register/verify-code` -> 远端 `POST /api/auth/register/verify-code`
  - 本地 `POST /program-auth/register/complete` -> 远端 `POST /api/auth/register/complete`
- 当远端返回结构化失败时，本地后端透传其 `request_id`；当本地直接遇到 DNS 失败、连接超时、非 JSON 响应或本地转发异常时，本地后端必须自行生成 `request_id` 并返回给前端，保证失败包络不破口。

### 远端控制面

- 需要提供三段式注册接口，而不是继续只暴露“发码 + 注册”。
- 风控、验证码状态、一次性票据都应由远端统一管理。

## 错误处理

- 发码失败：停留在邮箱页，提示“无法继续注册，请稍后重试”。
- 验证码错误、过期或会话失效：停留在验证码页，统一提示“验证码错误或已失效，请重新获取”。
- 验证次数过多：停留在验证码页，并要求重新发码。
- 票据过期：第三步提交失败后强制退回第二步。
- 账号名重复：第三步明确提示“账号名已被使用”。
- 密码不合规：第三步明确提示密码规则问题。
- 网络断开、DNS 失败、请求超时等非 HTTP 错误：统一映射为 `REGISTER_SERVICE_UNAVAILABLE`，停留当前步骤，不自动重试，只允许用户手动再次提交。

## 验证策略

### 前端

- 渲染测试覆盖三步状态切换。
- 非法邮箱时按钮禁用，且不会触发发码请求。
- 发码成功自动进入验证码页。
- 未通过验证码时不能进入设置密码页。
- `verification_ticket` 缺失或失效时不能注册成功。
- `REGISTER_TICKET_INVALID_OR_EXPIRED` 必须触发退回第二步。
- `REGISTER_CODE_ATTEMPTS_EXCEEDED` 必须触发“重新获取验证码”状态。

### 本地后端

- 路由测试覆盖三接口存在且参数透传正确。
- 错误映射测试覆盖“上游风控失败 -> 本地模糊提示”。
- 错误码映射测试覆盖三步状态切换所依赖的全部 `error_code`。

### 远端控制面

- 单元测试覆盖邮箱标准化、限流、验证码重试上限、票据一次性使用。
- 集成测试覆盖“发码 -> 验码 -> 完成注册”的完整成功链。
- 集成测试覆盖临时邮箱、高频请求、重复票据使用、验证码过期等失败链。
- 额外覆盖以下负例：重复发送后旧验证码失效、同票据并发提交只有一次成功、同邮箱跨安装实例触发限流、会话过期后必须重新发码。

## 成功判定

满足以下条件即视为本设计落地正确：

- 用户在注册流程里只能按“邮箱 -> 验证码 -> 账号名与密码”顺序推进。
- 前端无法在邮箱格式非法时触发发码请求。
- 后端能在发码阶段拦截明显异常邮箱和高频请求。
- 验证码通过后才会生成短时一次性注册票据。
- 没有有效票据时，最终注册接口不能创建账号。
