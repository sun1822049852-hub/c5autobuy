# Agent Memory

本文件只保留跨会话稳定有效的协作记忆。变动频繁、一次性步骤、临时排障过程不应写入。

## 稳定约束

- 子 agent 模型属于特殊硬约束：仅允许 `gpt-5.2`、`gpt-5.3-codex`、`gpt-5.4`（含同代 codex 变体）；默认禁用任何 `gpt-5.1*`，除非用户在当前会话明确授权。
- 会话级过程记录默认落到 `docs/agent/session-log.md`，并按时间顺序追加。
- “会话日志 + 记忆文件”为持续开启机制：发生仓库改动后必须更新会话日志；产生稳定约束后必须同步记忆文件。
- 记忆提炼原则：只有可复用、可执行、可验证的约束与决策才写入本文件。

## 已确认偏好

- 用户希望保留“会话日志 + 记忆文件”机制，用于跨会话承接上下文，而不是仅靠即时聊天历史。
- 用户不希望用函数名、文件路径、线程名来解释问题；默认应以模块职责、链路作用、等待点、边界条件与架构权衡来沟通，代码标识最多作为补充注脚。
- `autobuy.py` 属于历史参考文件；真实运行与后续需求修改统一落在 `app_backend/` 与 `app_desktop_web/`，不得再把行业务逻辑修复写回 `autobuy.py`。
- `查询 -> 命中 -> 购买` 是项目核心主链路；任何可能拖慢该链路时延、吞吐或稳定性的修改，都必须先上报并获得确认，不能直接实现。
- 用户当前追求“极限低延迟”：查询命中到购买提交必须优先，普通查询事件/统计/运行态广播，以及购买成功后的本地容量扣减、切仓判断、远端仓库校准、快照/统计/状态写回，默认走后台异步；只有账号认证失效类信号保持同步处理。
- 本仓当前只保留一个主远端：`origin` 指向用户自己的 GitHub 仓库 `git@github.com:sun1822049852-hub/c5autobuy.git`；后续默认不再依赖 Gitee。
- 查询侧到购买侧的主链路桥接口径已确认：查询命中优先直达购买侧 async fast-path，不再优先经过 intake 队列；购买侧对“全部账号忙碌”的命中只保留 `50ms` 本地豁免窗口，不再做固定间隔轮询，而是等待账号释放/恢复/扩容触发的 idle 信号唤醒，窗口内抢到空闲账号就立即派发，超时仍忙则直接丢弃，不进入等待队列。
- 购买调度热路径已确认采用“账号按代理桶常驻待命池，命中按桶直取”的结构：账号在恢复可接单或释放出并发余量时主动回到对应待命桶；主链不再允许为每次命中扫描总可用账号名单，总名单仅保留给活跃账号统计与兼容性接口。
- fast-path 热路径继续收薄：命中入口的“运行中”判断不得依赖完整 `snapshot`；`queued`/`duplicate`/`dropped_busy_accounts_after_grace` 这类中间命中态不再触发全量 `purchase_runtime.updated` 广播；命中统计标准化与 backlog 过期清理不得占用 fast-path 同步热路径。
- 购买侧“最近事件”已拆成两层：运行页不再展示也不再依赖它，`/purchase-runtime/status` 与 runtime update 广播默认返回空 `recent_events`；真实最近购买日志仅保留给诊断链路，并通过旁路缓冲异步落库/落缓存，避免把人类可见信息上报重新拉回主链。
- 购买成功件数的稳定口径已确认：运行态 `purchase_success_count`、按账号/按商品聚合统计，以及 submit-order 统计事件里的 `success_count`，都必须按支付接口返回的真实 `purchased_count` / `successCount` 记账；`submitted_product_count` 只表示本次批次载荷里的商品条目数，不能再拿它当成功件数上限。若后续再次出现“总购买件数与成功件数对不上、成功数量一多就少记”，优先检查 `app_backend/infrastructure/purchase/runtime/purchase_stats_aggregator.py` 与 `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py` 中是否又把 `purchased_count/successCount` 裁剪到 `piece_count/submitted_count`。
- 购买侧去重当前已确认两条稳定约束：认货标准保持“按磨损计算结果”不动，不改成按原始挂单 `id`；固定去重窗默认采用 `10s`，优化方向优先是降低去重账本维护成本（到期顺序清理），而不是新增更复杂的去重层次。
- 白名单页 `open-api` 的原始 Edge 复用链路现在会在 clone 出来的临时浏览器 session 启动前，续期 Chromium cookie 库中现有 `c5game.com` cookies 的本地过期时间；这只影响白名单页浏览器链，不改购买链请求头里的 `cookie_raw`/`x-access-token` 机制。
- 账号中心“新增账号登录成功”已确认为关键保护行为：登录主链不得依赖浏览器 profile 持久化成功，Windows 上活跃 Chromium session 的锁文件只能影响后续 best-effort 落盘，不能反向打断登录成功返回。登录结果仍可立即写入 `profile_root/profile_directory/profile_kind` 元数据，但真实 `persist_session()` 必须后置到浏览器退出后的 cleanup，或以同等的非阻断方式执行。
- 账号中心“新增账号 -> 登录 -> 回写账号”还有一条稳定归并规则：`c5_user_id` 只能在登录成功后拿到，因此归并必须发生在捕获登录结果之后；只要仓库里已存在同 `c5_user_id` 的账号，无论这次登录起点是普通空账号壳还是 API-only 来源，都应优先把登录结果并回已有账号，不能把同一个 `c5_user_id` 再写进新壳账号里。`API-only` 的特殊性只体现在“未命中已有账号时允许派生一个新的已登录账号”，不体现在“是否允许归并回老账号”。
- 白名单页 `open-api` 的复用链还有一条稳定优先级：优先复用仍存活的登录 `debugger_address`；若登录窗口刚关、最新登录态还没稳定落到 canonical profile，则优先复用本次登录的 `login_session_root`；只有上述两者都不可用时，才退回 bundle 中的保存型 `profile_root`。否则“登录刚成功/刚关窗就点添加白名单”会误拉旧 profile，重新落到登录页。
- 账号中心浏览器扫货开关新增一条稳定产品约束：只有“首次绑定成功”才默认关闭浏览器扫货。实现口径为首次把登录身份写入目标账号时同步写入 `token_enabled=False` 与 `browser_query_disabled_reason="manual_disabled"`；已有登录身份的老账号重登，或登录结果并回已有老账号时，必须保留该账号当前的浏览器扫货开关，不得静默覆盖。
- 账号中心“浏览器查询”开关的“打开”动作现已冻结为程序会员细粒度放权：后端 action 固定为 `account.browser_query.enable`，只有快照显式授予该权限时才允许从关闭切到开启；未授予时前端必须弹窗提示“当前此功能未开放”，但关闭浏览器查询与其它账号编辑动作不因此一并锁死。
- 仓库级 `AGENTS.md` 已明确把“既有数据获取链路、既有数据保存/回写/持久化链路”提升为关键行为；后续只要改动数据来源、字段映射、保存时机、写入目标、浏览器 session/profile/cookie 复用与持久化逻辑，默认都要先说明改动边界、验证方式与回退路径，不能再静默修改。
- 本项目 backend 测试若在导入阶段因缺少 `xsign` 失败，后续默认先检查测试入口兜底（如 `tests/backend/conftest.py`）、统一测试脚本或现有 stub/fallback，不再优先采用单次命令临时注入；同类环境坑重复出现时应沉淀为仓库规则或自动兜底。
- 程序会员 / 程序账号的产品语义已冻结：本地桌面主线只有一份共享业务数据；程序账号只承载远端鉴权与会员权限，不拥有本地数据；切换程序账号只改变权限态，不切换本地工作区；登出或会员失效后本地数据仍可只读查看，但关键动作必须统一锁死；切到有会员的账号后在原工作区上直接恢复可用。
- 程序账号入口 UI 也已冻结一条稳定约束：左侧侧栏只允许显示最小登录状态摘要，即 `未登录` 或当前 `username`，不得再把权限说明、注册/找回密码、到期时间等细节重新塞回侧栏；具体账号操作统一在屏幕中央弹窗中完成，且已登录时弹窗只显示当前账号状态与 `刷新状态` / `退出`，不再显示登录表单。
- C5 账号登录任务的用户可见状态文案已冻结为“集中映射、统一复用”模式：唯一维护点是 `app_desktop_web/src/features/account-center/login_task_state_labels.js`；账号中心登录抽屉、诊断页登录任务标签页、账号中心日志中的状态显示都必须走这份映射，后续若用户要求改某个状态文案，应优先改这里而不是在各组件内散改。
- 用户可见的正式入口文案继续冻结一条风格约束：普通用户直接能看到的页眉/眉标默认优先中文，不再保留 `ACCOUNT CENTER`、`PROGRAM ACCESS`、`Diagnostics` 这类英文眉标；只有显式本地调试分支里的提示，例如 `本地调试模式`，才允许保留调试口径作为区分标记。
- 主导航按钮也已冻结一条 UI 文案约束：不再展示英文状态签条 `Live`；导航只保留中文功能名本身，不再额外挂英文视觉标签。
- 配置管理里的商品级手动暂停展示也已冻结一条 UI 约束：暂停状态必须作为商品行内最后一列 `状态` 展示，不能再挂在行外独立按钮位；界面只显示图形，`manual_paused=true` 用红色三角形，`manual_paused=false` 用绿色双竖线，删除模式则在同一格位原地替换成 `-` 删除按钮。
- 程序账号注册链路已冻结为“三步前端 + 三接口后端”结构：第一步仅输邮箱并在远端发码阶段做风控，第二步独立验证验证码，第三步仅在验码成功后凭一次性 `verification_ticket` 设置账号名与密码完成注册；前端本地正则只做粗校验，真正的防刷判断必须留在远端统一鉴权。
- 程序账号注册发码链路又新增一条稳定反绕过约束：本地 backend 必须把 program access 稳定 `device_id` 作为远端 `install_id` 透传到注册 `send-code / verify-code / complete` 三接口；60 秒发码冷却不能靠“修改邮箱”绕过，renderer 回到邮箱页时也必须保留冷却并优先采用远端 `retry_after_seconds`；`qq.co` 这类已确认的公共邮箱 typo 域名按 `REGISTER_INPUT_INVALID` 拦截。
- 程序账号三步注册的发布约束也已冻结：只有当远端 `send-code / verify-code / complete` 三接口全部就绪时，本地后端才可把 `registration_flow_version` 切到 `3` 放行新 UI；否则桌面端必须继续停留在旧的两接口注册链路，不能让本地 UI 先于远端能力切换。
- 程序账号注册链路还有一条 renderer 启动约束：只要当前桌面 backend 已 `ready`，renderer 就必须从当前 `apiBaseUrl` 拉取 `/app/bootstrap` 来水合 `program_access`，不能把 bootstrap 仅限于 `remote` 模式。否则 `main_ui_node_desktop.js` 这类 `embedded` 桌面虽然本地 backend 已返回 `registration_flow_version=3`，窗口仍会卡在前端默认值 `registrationFlowVersion=2`，错误回退到旧一屏式注册 UI。
- 截至 `2026-04-23`，远端会员控制面 `http://8.138.39.139:18787` 已完成注册 v3 rollout：`/api/auth/register/readiness`、`/api/auth/register/send-code`、`/api/auth/register/verify-code`、`/api/auth/register/complete` 均已上线；正式桌面入口 `main_ui_node_desktop.js` 对应的本地 backend bootstrap 应返回 `remote_entitlement / packaged_release / registration_flow_version=3`，而 `main_ui_node_desktop_local_debug.js` 继续保持 `local_pass_through / prepackaging / registration_flow_version=2`。
- 当前会员控制面已部署到远端 `8.138.39.139:18787`，后台入口为 `/admin`；该入口当前用于测试联调。稳定收口要求一并冻结：管理端口不得长期保持 `0.0.0.0/0` 全网开放，正式发行前至少要改成“仅用户固定公网 IP 可访问”，或进一步收口为 `80/443 + 域名/反向代理/额外鉴权`。
- 当前桌面发行主线已确认只能以根工作树 `master` 为准；`main_ui_node_desktop.js` 是唯一真实桌面主入口。任何 side worktree 若删除或替换这条真实入口链路，都只能作为局部回收源，不能直接用于打包发行。
- 当前桌面对外启动口径已收口为 JS-only：`main_ui_node_desktop.js` 用于模拟用户态与正式程序会员鉴权测试，`main_ui_node_desktop_local_debug.js` 用于本地放行调试；顶层 Python 包装入口已移除，`app_backend/main.py` 只保留给 JS 桌面壳内部拉起 backend 使用。后续不得再通过“删 release 配置文件”这种隐式方式切模式，也不得再把 Python 包装壳恢复成对外主入口。
- `feature/membership-auth-v1` 已确认为过时的本地多租户漂移源并从现场移除；后续会员排查只参考根工作树 `master`、`feature/local-program-access-extension` 与 `feature/program-control-plane-chunk1`。
- 当前桌面打包控制面配置已回到根主线：`app_desktop_web/program_access_config.cjs` 负责读取 `client_config.json` / `client_config.release.json` / 环境变量中的 `controlPlaneBaseUrl`，默认 release 配置文件为 `app_desktop_web/build/client_config.release.json`，当前值固定为 `http://8.138.39.139:18787`；本地放行调试则固定走 `app_desktop_web/build/client_config.local_debug.json`。这两份静态配置都不得在“清理过期产物”时当作临时构建垃圾删除。Electron 安装器约束为 `nsis.oneClick=false`、允许用户自定义安装目录、创建桌面快捷方式与开始菜单快捷方式。
- 当前本地 Windows 打包环境不具备 `winCodeSign` 归档所需的 symlink 权限；为保证常规用户态可直接出包，`app_desktop_web/electron-builder.config.cjs` 已固定 `win.signAndEditExecutable=false`，绕过 `rcedit` / `winCodeSign` 下载解压链。后续若要恢复 EXE 元信息编辑或签名，再单独切到具备 Developer Mode / 提权 / 专用签名环境的发行机处理。
- 当前桌面程序整体品牌已统一为 `C5 交易助手`：安装包名、Electron 窗口标题、HTML title、侧栏品牌标题与账号首页主标题均使用该名称；内部功能名如 `账号中心`、`配置管理`、`扫货系统` 可保留，不改本地数据目录名。
- Windows 源码态桌面若再次出现“程序完全打不开”，当前已确认一条稳定排障顺序：先看 `main_ui_node_desktop.js` 启动器是否误把缺失的 `electron/cli.js` 当成阻塞，再检查 `app_desktop_web/node_modules/electron/checksums.json`、`dist/electron.exe`、`dist/chrome_100_percent.pak` 是否齐全。`electron/install.js` 的 `isInstalled()` 只看 `version/path.txt/electron.exe`，无法识别 `.pak` 缺失这类半损坏现场；若包本体连 `checksums.json` 都没了，优先最小重装 `electron@37.2.0`（如 `npm install electron@37.2.0 --no-save --package-lock=false`），不要误判成业务代码故障。
- 程序账号注册弹窗新增一条稳定恢复约束：三段式注册在第二段验证码页时，只在当前 renderer 会话内保留草稿；关闭弹窗、切页后再次打开必须直接回到第二段，并保留脱敏邮箱、`register_session_id` 与当前倒计时。只有主动切到“登录/找回密码”、点击“修改邮箱”或注册成功时，才允许清空这份注册草稿。
- 程序账号弹窗视觉也新增一条稳定 UI 约束：默认 `program_auth_required / 请先登录程序会员` 不再作为顶部异常提示展示；登录/注册/找回密码输入区默认使用输入框内 `placeholder`，右上角关闭控件保持红底正方形 `X`，但访问名仍必须是“关闭”。
- 当前桌面发行瘦身主线已冻结：packaged release 不再允许整包内置开发 `.venv`；首刀方案固定为“首次启动从 Python 官方下载固定版本 Windows embeddable runtime，失败则阻断进入程序并允许重试”。开发态仍保留 `.venv/Scripts/python.exe` 解析；实现时不得回到“复制整套开发环境发行”的旧路径。
- packaged embeddable Python runtime 还有一条稳定隔离约束：`python311._pth` 必须显式包含应用资源根目录，且不得重新启用 `import site`；packaged backend 子进程环境必须同时设置 `PYTHONNOUSERSITE=1`。否则用户全局 `site-packages` / editable hook 会污染 `sys.path`，导致打包内的 `xsign.py`、`app_backend` 等模块被错误遮蔽或导入失败。
- 打包验证新增一条稳定执行约束：除非用户在当前会话主动明确指定，否则不得把“重新生成安装包 / 执行 `build:win`”当成默认验证步骤；常规发行验尸优先停留在 `pack:win`、现有 installer 体积核对或 `win-unpacked` 结构检查。
- 扫货系统商品卡片的统计口径新增一条稳定产品约束：停止扫货后，所选配置的商品级 `查询次数 / 命中 / 成功 / 失败` 必须继续显示当天累计值，不得因 stop 动作清空；清空边界按自然日切换，而不是按开始/停止按钮切换。
- 当前 embedded 桌面启动口径新增一条稳定交互约束：主界面壳必须先亮，不再把 renderer 首次加载硬卡在本地 backend `/health` 之后；backend `ready` 后再通过主进程 bootstrap 更新把真实 `apiBaseUrl/backendStatus` 推给 renderer，并在此之前禁止首页页面抢跑数据请求。
- `app_backend.main` 的默认 `app` 现已冻结为懒加载口径：导入模块本身不得立刻执行 `create_app()`；只有显式访问 `app_backend.main.app` 时才允许首次构建并缓存默认实例，避免桌面 embedded 启动重复建 app。
