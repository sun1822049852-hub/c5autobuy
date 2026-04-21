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
- 仓库级 `AGENTS.md` 已明确把“既有数据获取链路、既有数据保存/回写/持久化链路”提升为关键行为；后续只要改动数据来源、字段映射、保存时机、写入目标、浏览器 session/profile/cookie 复用与持久化逻辑，默认都要先说明改动边界、验证方式与回退路径，不能再静默修改。
- 本项目 backend 测试若在导入阶段因缺少 `xsign` 失败，后续默认先检查测试入口兜底（如 `tests/backend/conftest.py`）、统一测试脚本或现有 stub/fallback，不再优先采用单次命令临时注入；同类环境坑重复出现时应沉淀为仓库规则或自动兜底。
- 程序会员 / 程序账号的产品语义已冻结：本地桌面主线只有一份共享业务数据；程序账号只承载远端鉴权与会员权限，不拥有本地数据；切换程序账号只改变权限态，不切换本地工作区；登出或会员失效后本地数据仍可只读查看，但关键动作必须统一锁死；切到有会员的账号后在原工作区上直接恢复可用。
- 当前会员控制面已部署到远端 `8.138.39.139:18787`，后台入口为 `/admin`；该入口当前用于测试联调。稳定收口要求一并冻结：管理端口不得长期保持 `0.0.0.0/0` 全网开放，正式发行前至少要改成“仅用户固定公网 IP 可访问”，或进一步收口为 `80/443 + 域名/反向代理/额外鉴权`。
- 当前桌面发行主线已确认只能以根工作树 `master` 为准；`main_ui_node_desktop.js` 是唯一真实桌面主入口。任何 side worktree 若删除或替换这条真实入口链路，都只能作为局部回收源，不能直接用于打包发行。
- `feature/membership-auth-v1` 已确认为过时的本地多租户漂移源并从现场移除；后续会员排查只参考根工作树 `master`、`feature/local-program-access-extension` 与 `feature/program-control-plane-chunk1`。
- 当前桌面打包控制面配置已回到根主线：`app_desktop_web/program_access_config.cjs` 负责读取 `client_config.json` / `client_config.release.json` / 环境变量中的 `controlPlaneBaseUrl`，默认 release 配置文件为 `app_desktop_web/build/client_config.release.json`，当前值固定为 `http://8.138.39.139:18787`；这份 `build/client_config.release.json` 是发行必带静态配置，不得在“清理过期产物”时当作临时构建垃圾删除。Electron 安装器约束为 `nsis.oneClick=false`、允许用户自定义安装目录、创建桌面快捷方式与开始菜单快捷方式。
- 当前本地 Windows 打包环境不具备 `winCodeSign` 归档所需的 symlink 权限；为保证常规用户态可直接出包，`app_desktop_web/electron-builder.config.cjs` 已固定 `win.signAndEditExecutable=false`，绕过 `rcedit` / `winCodeSign` 下载解压链。后续若要恢复 EXE 元信息编辑或签名，再单独切到具备 Developer Mode / 提权 / 专用签名环境的发行机处理。
- 当前桌面程序整体品牌已统一为 `C5 交易助手`：安装包名、Electron 窗口标题、HTML title、侧栏品牌标题与账号首页主标题均使用该名称；内部功能名如 `账号中心`、`配置管理`、`扫货系统` 可保留，不改本地数据目录名。
- Windows 源码态桌面若再次出现“程序完全打不开”，当前已确认一条稳定排障顺序：先看 `main_ui_node_desktop.js` 启动器是否误把缺失的 `electron/cli.js` 当成阻塞，再检查 `app_desktop_web/node_modules/electron/checksums.json`、`dist/electron.exe`、`dist/chrome_100_percent.pak` 是否齐全。`electron/install.js` 的 `isInstalled()` 只看 `version/path.txt/electron.exe`，无法识别 `.pak` 缺失这类半损坏现场；若包本体连 `checksums.json` 都没了，优先最小重装 `electron@37.2.0`（如 `npm install electron@37.2.0 --no-save --package-lock=false`），不要误判成业务代码故障。
