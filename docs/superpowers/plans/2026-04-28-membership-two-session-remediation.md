# 2026-04-28 Membership Remaining Issues

> 这是一份给“刚刚改过会员链路的既有 Agent”共读的公共错点清单。  
> 不是重新分工文档，不是假设读者不知道自己改过什么。  
> 读到这份文档的 Agent，应该自己根据刚才改过的内容，判断哪些错点和自己有关，然后修正。  
> 不要重做全仓探索。不要把已经修好的主 blocker 重新打开。

## 这份文档怎么用

- 先读完这份文档。
- 只看“还没收干净的错”。
- 结合你自己刚才改过的文件和链路，自行判断哪些错点归你修。
- 不需要在这份文档里找“你被分配到哪条线”；这里没有分线。
- 改完后，自己补 focused 验证，并更新 `docs/agent/session-log.md`。

## 当前本地现场

- 当前工作树在写本文档前是干净的：
  - `git status` clean
  - `git diff --stat` empty
- 当前会员相关最近提交主要是：
  - `649dd49 fix: harden membership control plane blockers`
  - `5ba1cfc feat: enforce runtime revoke push stop`
- 本地 fresh focused 验证已经跑过且通过：
  - `npm --prefix program_admin_console run test:store`
  - `npm --prefix program_admin_console run test:server`
  - `npm --prefix program_admin_console run test:ui`
  - `npm --prefix program_admin_console run test:deploy-script`
  - `C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_program_auth_routes.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_remote_control_plane_client.py tests/backend/test_program_runtime_control_service.py tests/backend/test_program_runtime_control_end_to_end.py`
    - 结果：`71 passed`
  - `C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)/.venv/Scripts/python.exe -m pytest -q tests/backend/test_query_runtime_service.py -k program_runtime_control`
    - 结果：`2 passed, 51 deselected`

## 已经修好的点，不要误当成待修项

下面这些在本地仓内已经收口，除非你自己后续改动把它们回归打坏，否则不要再重开：

- 会员到期后，`runtime-permit` 已能立即失效。
- 设备撤销后，已在线 runtime-control 客户端已能立即收到 revoke 并停机。
- 非有效会员 / disabled 用户不再把 `permission_overrides` 叠回实际 entitlements。
- 清空到期日不再把限时会员放大成长期/永久会员。
- 未知权限名不能再被任意签发给客户端。
- 部署脚本不再把签名私钥正文拉回部署机，而是远端本机派生 `PROGRAM_ADMIN_SIGNING_KID`。

## 还没收干净的错点

### 1. 注册发码接口仍然泄露“邮箱是否已注册”

- 现象：
  - `POST /api/auth/register/send-code`
  - 已注册邮箱直接返回 `403 REGISTER_SEND_DENIED`
- 真实风险：
  - 外部调用方可以低成本枚举已注册邮箱。
  - 可被继续用于撞库、钓鱼、邮件轰炸。
- 证据：
  - `program_admin_console/src/server.js:708-714`
- 修正要求：
  - 保留冷却、限流、审计和 `retry_after_seconds`
  - 只收敛“账号是否存在”的外部信号
  - 不要回退 v3 注册链路

### 2. 找回密码发码接口仍然泄露“账号是否存在”

- 现象：
  - `POST /api/auth/password/send-reset-code`
  - 不存在邮箱直接返回 `404 user_not_found`
- 真实风险：
  - 这条公网 auth surface 同样可以被直接用来做账号枚举。
- 证据：
  - `program_admin_console/src/server.js:1161-1163`
- 修正要求：
  - 保留邮箱格式错误、邮件服务未配置等真正需要暴露的前置校验
  - 只收敛“用户存在性”这个外部信号
  - 不要把重置验证码冷却逻辑打散

### 3. `trustProxy` 口径过宽，`X-Forwarded-For` 第一段可被直接信任

- 现象：
  - 打开 `PROGRAM_ADMIN_TRUST_PROXY=true` 后，来源 IP 直接取 `X-Forwarded-For` 第一段
  - localhost-only bootstrap 也复用这套来源判断
- 真实风险：
  - 如果部署边界配错，外部请求可伪造来源地址
  - `bootstrap only allowed from localhost` 这类假设可能被头部伪装穿透
- 证据：
  - `program_admin_console/src/server.js:216-223`
  - `program_admin_console/src/server.js:473-476`
- 修正要求：
  - 把“可信代理”收成严格部署契约
  - 不要再信任来路不明的首段 XFF
  - 要有显式测试覆盖伪造 header 的情况

### 4. 发布脚本和公网 smoke 还没把 `/api/admin/*` 暴露边界验死

- 现象：
  - 目前 HTTPS smoke 会检查公网 `/admin` 不可达
  - 但没有显式检查公网 `/api/admin/*` 也被拒绝
  - loopback smoke 和 public smoke 的结果边界不够清楚
- 真实风险：
  - 文档口径是“公网只放 `/api/health` 与 `/api/auth/*`，拒绝 `/admin` 与 `/api/admin/*`”
  - 但自动验收没有把这条最关键的公网边界锁死
- 证据：
  - `program_admin_console/tools/deployProgramAdminRemote.ps1:424-487`
  - `program_admin_console/README.md:69-82`
  - `AGENTS.md:40-45`
- 修正要求：
  - deploy smoke 需要明确区分：
    - 只跑了 loopback smoke
    - 额外跑了 public HTTPS smoke
  - public smoke 至少显式验证 `/api/admin/*` 不可公网访问
  - 不要把“脚本绿了”误写成“公网边界已安全”

### 5. 过期 refresh session 仍然会被算作“活跃设备”

- 现象：
  - 活跃设备统计和设备列表只看 `status='active'` 且 `revoked_at=''`
  - 没把 `expires_at` 过期排除出去
- 真实风险：
  - 运营会把已经自然失效的设备误判成仍在线、仍可用、仍需手动吊销
  - 会直接误导“当前活跃设备数”
- 证据：
  - `program_admin_console/src/controlPlaneStore.js:620-626`
  - `program_admin_console/src/controlPlaneStore.js:1045-1061`
  - `program_admin_console/ui/app.js:353-362`
- 修正要求：
  - 统一“活跃设备”的 truth rule
  - 列表和统计都要按同一语义

### 6. 控制台展示仍可能误导运营判断当前会员是否有效

- 现象：
  - 详情页对 disabled / inactive 的说明比之前清楚了
  - 但列表仍直接显示原始 `membership_plan` 和原始到期时间
- 真实风险：
  - 运营快速扫列表时，容易把 disabled 或实际上已失效的人看成仍是 `member`
  - 这里不是“权限真泄漏”，而是“后台页面仍可能误导人”
- 证据：
  - `program_admin_console/ui/app.js:303-323`
  - `program_admin_console/ui/app.js:337-344`
- 修正要求：
  - 明确区分“原始设置”与“当前实际生效”
  - 不要回退已修好的 disabled / non-member entitlement 逻辑

### 7. 签名链仍是单钥匙硬切换，缺少平滑轮换路径

- 现象：
  - 控制台只公开单个 `kid + public_key_pem`
  - signer 只持有一把当前私钥
  - 客户端遇到新 key 时会直接替换本地缓存
- 真实风险：
  - 主泄露面已经收住了，但正式轮换时仍缺少重叠窗口
  - 旧 token 未自然老化前切新 key，容易出现硬切换问题
- 证据：
  - `program_admin_console/src/entitlementSigner.js:57-150`
  - `program_admin_console/src/server.js:434-438`
  - `app_backend/infrastructure/program_access/remote_entitlement_gateway.py:418-436`
  - `app_backend/infrastructure/program_access/entitlement_verifier.py`
- 修正要求：
  - 增加平滑轮换能力
  - 不要弱化验签
  - 不要把任务扩成密钥托管系统重构

### 8. 本地 refresh 材料读取失败，仍会塌成“未登录”

- 现象：
  - 本地 secret/material 读取失败时，gateway 直接把 refresh token 当成不存在
  - 后续 `refresh()` 走到 `PROGRAM_AUTH_REQUIRED_CODE`
- 真实风险：
  - 本地材料损坏、读取失败、解密失败，会被误报成“用户未登录”
  - 用户和运维都会被错误引导，排障方向会跑偏
- 证据：
  - `app_backend/infrastructure/program_access/remote_entitlement_gateway.py:563-570`
  - `app_backend/infrastructure/program_access/remote_entitlement_gateway.py:119-127`
- 修正要求：
  - 保持 fail-closed
  - 但必须把“本地材料读取失败”和“真的未登录”区分开
  - 路由层、scheduler、summary 至少要保留这个区别

## 所有读到这份文档的 Agent 必须遵守

- 不要重做全仓探索。
- 只修和你自己刚才改过的内容直接相关的错点。
- 若发现文档和现场冲突：
  - 先指出差异
  - 再以代码、测试和 fresh 运行结果为准
- 若这轮改动触碰 `program_admin_console` 的用户可见行为或远端控制面行为：
  - 要么完成远端同步、容器替换和最小 smoke
  - 要么明确写“本地已改，远端未同步”
- 改完后必须：
  - 补 focused 验证
  - 更新 `docs/agent/session-log.md`
  - 明确写清：
    - 你修了哪些错点
    - 哪些故意没碰
    - 远端是否同步

## 可直接复制给任意一个既有 Agent 的通用提示词

你就是刚才已经改过这轮会员链路的人，不是第一次接手的新 Agent。不要重做全仓探索。先读取：

- `docs/superpowers/plans/2026-04-28-membership-two-session-remediation.md`
- `docs/agent/session-log.md` 最新相关条目
- `docs/agent/memory.md` 最后一条会员上线强制回归约束
- `git status`

然后按下面规则工作：

1. 先用人话复述：你刚才已经改过一部分，现在只根据这份公共错点清单，修和你自己刚才改动直接相关的剩余问题。
2. 不要让我重新给你分工；你自己根据刚才改过的链路判断哪些错点归你修。
3. 不要重开已经修好的主 blocker，除非你亲手把它改坏了。
4. 改完后只复跑和你本次修正直接相关的 focused 测试，不要拿已有绿灯直接当安全。
5. 如果改到 `program_admin_console` 的用户可见行为或远端控制面行为，收口时必须明确远端是否同步；没同步就直接写“本地已改，远端未同步”。
6. 最后更新 `docs/agent/session-log.md`，写清：
   - 本次认领并修掉了哪些错点
   - 哪些错点不归你这轮处理
   - fresh 验证结果
   - 远端同步状态
