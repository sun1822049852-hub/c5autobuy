# Program Access Registration Cooldown Hard Lock And Email Validation Design

**Goal:** 修复程序账号注册发码的两个缺口：用户不能再通过“修改邮箱”绕过 60 秒冷却；明显不完整的邮箱地址（例如 `1822049852@qq.CO`）必须在发码前被拦下。

**Scope:** 只修改程序账号注册发码链路，不改登录、找回密码、注册三步主链与其他业务主流程。

## 背景与根因

- 当前 renderer 在第二步点击“修改邮箱”时会直接清空本地 `registerResendCooldownSeconds`，导致用户切回第一步后看不到剩余冷却。
- 当前远端 control-plane 只对同邮箱做 60 秒冷却；同一安装实例在 10 分钟窗口内允许最多 3 次发码，因此换邮箱仍可继续发码，形成绕过。
- 当前前后端邮箱校验都使用过宽的正则 `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`，像 `qq.CO` 这种明显的常见域名 typo 会被放行。
- 当前本地 backend 路由在错误路径只保留 `code/message`，会吞掉 control-plane 返回的 `retry_after_seconds`，导致 renderer 无法按失败响应继续展示冷却。

## 不可改变项

- 不改登录链。
- 不改找回密码链。
- 不改 `查询 -> 命中 -> 购买` 主链。
- 不改已完成的注册三步状态机结构：邮箱 -> 验码 -> 设置账号密码。

## 方案

### 1. 冷却锁定改为“设备/安装实例不可绕过”

- 远端 `/api/auth/register/send-code` 继续保留同邮箱 60 秒冷却。
- 额外新增同安装实例 60 秒硬冷却；当前请求未携带设备指纹时，以 `install_id` 为主锁。
- 若命中硬冷却，无论邮箱是否变化，都返回 `REGISTER_SEND_RETRY_LATER` 与剩余 `retry_after_seconds`。
- 这条 60 秒限制只约束“再次发码”，不影响用户在界面上修改输入邮箱文本。
- 本地 backend 不生成新的安装实例 ID；统一复用 program access 的稳定 `device_id`，并在 `/register/send-code`、`/register/verify-code`、`/register/complete` 三个远端调用里把它作为 `install_id` 透传，保证同一桌面实例上的注册三步都命中同一把冷却锁。

### 2. Renderer 改邮箱时不再清空冷却

- 第二步点击“修改邮箱”后仍回到第一步，但保留当前剩余冷却秒数。
- 第一页若存在剩余冷却：
  - “发送注册验证码”按钮保持禁用；
  - 沿用后端给出的剩余秒数展示倒计时；
  - 用户可编辑邮箱，但不能靠改邮箱立即再次发码。
- 若发码失败且错误包络带 `retry_after_seconds`，前端优先使用该值覆盖当前冷却。

### 3. 邮箱校验收口

- renderer 与远端 control-plane 统一采用更严格的基础邮箱校验；本地 backend 不重复做一层邮箱格式判断，只透传请求与错误：
  - local/domain 不允许空白；
  - domain 必须包含至少一个 `.`；
  - 顶级域长度限定在合理范围内；
  - 仅接受字母数字及常见邮箱符号。
- 额外拦截一组明确的常见公共邮箱 typo 域名，首刀至少覆盖 `qq.co`。
- 被拦截时统一返回/显示 `REGISTER_INPUT_INVALID`，不进入发码流程。

## 数据流与包络

- control-plane 命中冷却时继续返回：
  - `error_code=REGISTER_SEND_RETRY_LATER`
  - `retry_after_seconds=<剩余秒数>`
- Python remote client 兼容 control-plane v3 的错误包络，优先读取 `error_code`，不再只认旧 `reason`。
- 本地 backend `/program-auth/register/send-code` 在错误 detail 中必须透传 `retry_after_seconds`，不得吞掉。
- renderer 从错误 JSON 中解析 `retry_after_seconds`，并更新本地冷却展示。

## 验证

- renderer 测试：
  - 第二步点击“修改邮箱”后回到邮箱页，但剩余冷却仍在，且按钮禁用。
  - 命中 `REGISTER_SEND_RETRY_LATER` 时，失败响应中的 `retry_after_seconds` 会刷新前端冷却。
- control-plane server 测试：
  - 同一安装实例在 60 秒内用不同邮箱再次发码，返回 `429 + REGISTER_SEND_RETRY_LATER`。
  - `1822049852@qq.CO` 发码直接返回 `400 + REGISTER_INPUT_INVALID`。
- backend 测试：
  - route/gateway 会把 `retry_after_seconds` 透传给 renderer 可解析的错误 detail。
