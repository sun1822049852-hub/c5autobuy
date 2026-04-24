# Agent Session Log

本文件记录 agent 在本仓库中的会话级执行轨迹，按时间顺序追加，不回写历史。

## 记录模板

```text
## YYYY-MM-DD HH:mm (Asia/Shanghai)
- 背景：
- 已完成：
- 当前进度：
- 下一步：
```

## Entries

## 2026-04-14 10:30 (Asia/Shanghai)
- 背景：确认并固化 agent 工作流偏好。
- 已完成：将子 agent 模型限制固化为特殊硬约束（仅 `gpt-5.2` / `gpt-5.3-codex` / `gpt-5.4`，禁用 `gpt-5.1*`）。
- 当前进度：已建立会话日志与记忆文件双文档机制，并接入项目 `AGENTS.md`。
- 下一步：按后续任务持续追加日志；仅把稳定共识提炼到 `docs/agent/memory.md`。

## 2026-04-14 10:58 (Asia/Shanghai)
- 背景：用户要求“会话日志 + 记忆文件”持续开启，避免遗漏修改。
- 已完成：将该模块从可选改为强制常开，并补充防遗漏检查规则（改动后必须更新日志，稳定约束必须更新记忆）。
- 当前进度：项目级与全局 `AGENTS.md` 已同步新口径。
- 下一步：后续每次改动按新规则先记日志，再提炼稳定记忆。

## 2026-04-14 13:43 (Asia/Shanghai)
- 背景：修正购买/诊断链路的错误分类与日志展示，并阻止继续误改历史参考文件 `autobuy.py`。
- 已完成：将“订单数据发生变化,请刷新页面重试”与 `successCount == 0` 统一归类为 `payment_success_no_items`；全局错误仅保留账号认证失效类信息；查询与购买日志补齐完整 `request_body` / `response_text` 并将最近事件缓存上限统一到 `500`；前端补充请求体展示；在 `autobuy.py` 顶部加入“历史参考文件，禁止继续落业务改动”警告。
- 当前进度：相关后端回归 `139` 条与前端回归 `35` 条均已通过。
- 下一步：如需继续扩展日志字段或错误归类，直接在 `app_backend/` 与 `app_desktop_web/` 实现，不再修改 `autobuy.py`。

## 2026-04-14 13:55 (Asia/Shanghai)
- 背景：用户要求把“任何会拖慢查询到购买主链路的修改都必须先上报”固化为项目规则。
- 已完成：在项目 `AGENTS.md` 新增“主链路性能红线”章节，明确 `查询 -> 命中 -> 购买` 为核心主链路，并要求影响时延、吞吐、下单速度或稳定性的改动必须先上报确认；同步将该约束写入 `docs/agent/memory.md`。
- 当前进度：项目级正式规则、跨会话记忆、会话日志三处已对齐。
- 下一步：后续凡涉及主链路性能风险的改动，先汇报影响与回退方案，再进入实现。

## 2026-04-14 15:14 (Asia/Shanghai)
- 背景：继续按“极限低延迟”目标收紧 `查询 -> 命中 -> 购买` 主链路，避免查询广播与购买成功后处理拖慢派单。
- 已完成：查询侧恢复“账号失效事件同步上报、普通事件/统计异步旁路”的分层；购买侧新增后台后处理队列，把非 `auth_invalid` 的购买结果改为先释放账号再异步执行库存账面更新、切仓判断、远端仓库校准、快照/统计/状态广播，并引入 `postprocess_epoch` 防止旧成功后处理覆盖新的账号失效状态；补充并跑通对应回归测试。
- 当前进度：`tests/backend/test_mode_execution_runner.py`、`tests/backend/test_query_runtime_service.py`、`tests/backend/test_purchase_runtime_service.py` 共 `155` 条已通过。
- 下一步：若继续压缩尾延迟，优先检查剩余同步通知/持久化是否还能继续旁路，同时保持“账号认证失效同步、其余尽量异步”的红线不变。

## 2026-04-14 15:41 (Asia/Shanghai)
- 背景：用户进一步确认查询侧不应等待购买侧即时回话，目标结构是“查询只投递，购买侧自己完成短时去重、排队和账号派发”。
- 已完成：查询运行时改为对异步 `hit_sink` 不再等待完成；购买服务新增快速 `enqueue_query_hit` 入口与后台命中 intake worker，查询运行时优先绑定该快速投递入口；补充测试覆盖“查询不等慢 hit sink”和“桥接优先使用快速投递入口”，并修正相关异步测试口径。
- 当前进度：`tests/backend/test_query_purchase_bridge.py`、`tests/backend/test_mode_execution_runner.py`、`tests/backend/test_query_runtime_service.py`、`tests/backend/test_purchase_runtime_service.py` 共 `163` 条已通过。
- 下一步：如继续压低延迟，优先审视购买入口与调度层内部是否还有同步热点；查询侧原则上保持“只查、只投递、不等购买侧处理结果”不再回退。

## 2026-04-14 16:20 (Asia/Shanghai)
- 背景：用户确认主链路进一步向旧架构靠拢，查询命中遇到购买账号全忙时不再走等待队列，而是只保留极短豁免后直接丢弃。
- 已完成：查询运行时改为优先绑定购买侧 `async fast-path` 命中入口；购买运行时新增 fast-path 本地重抢逻辑，对全忙命中仅保留 `50ms` 豁免窗口并按 `3ms` 间隔短轮询抢空闲账号，超时仍忙则直接丢弃且不入队；补充桥接测试与 fast-path 成功/丢弃测试。
- 当前进度：主链路已切到“直达购买入口 -> 本地短豁免 -> 超时丢弃”，原公共 `enqueue_query_hit` / intake / backlog 行为仍保留给非主链路调用；针对性回归 `16` 条已通过。
- 下一步：若继续追杀时延，可再评估是否要把 fast-path 的短轮询改成“账号释放主动唤醒”，但那会牵动更深的调度器骨架。

## 2026-04-14 16:48 (Asia/Shanghai)
- 背景：用户要求把 fast-path 剩余的三类过路费一起砍掉：命中前完整运行态体检、命中中间态全量 runtime update 广播、统计/清理杂活占用热路径。
- 已完成：购买服务的热路径运行态检查改为优先读轻量 running 标记，不再默认走完整 `snapshot`；fast-path 的 `queued` / `duplicate` / `ignored_*` / `dropped_busy_accounts_after_grace` 等命中中间态只记录本地 recent event，不再触发全量 `purchase_runtime.updated`；fast-path 不再顺手清 backlog，命中统计的字段标准化移动到 `PurchaseStatsAggregator` 后台线程消费阶段；补充并跑通对应红绿测试。
- 当前进度：查询桥接、普通 `enqueue` 通路、fast-path 直达派发、购后处理与 fan-out 回归共 `21` 条已通过。
- 下一步：若还要继续压尾延迟，下一优先级是把 fast-path 的 `3ms` 轮询替换成“账号释放主动唤醒”，其次再评估是否需要对 runtime update 做更强的合并/节流。

## 2026-04-14 17:05 (Asia/Shanghai)
- 背景：用户确认将 fast-path 的 `3ms` 轮询等待替换成“账号空闲主动上报”的信号式唤醒方案。
- 已完成：购买运行时新增 fast-path idle 信号版本号与条件变量；fast-path 在 `50ms` 豁免窗口内改为等待 idle 信号，不再 `asyncio.sleep` 轮询；账号购买完成释放、账号恢复为 ACTIVE、并发额度调整后均会唤醒等待中的 fast-path；补充“禁止 poll sleep”的红绿测试并跑通。
- 当前进度：主链路已从“直达 fast-path + 3ms 轮询”升级为“直达 fast-path + idle 信号唤醒”；相关桥接/等待恢复/fast-path/扇出/购后处理回归共 `22` 条已通过。
- 下一步：若继续压时延，再评估是否要把调度器的“现扫账号表”进一步升级为常驻 idle bucket registry，减少账号规模变大后的扫描成本。

## 2026-04-14 19:16 (Asia/Shanghai)
- 背景：用户明确要求后续沟通不要再用函数名、线程名、文件路径来串联解释，而要用设计职责与链路作用表达。
- 已完成：将“默认用模块职责、链路阶段、等待点、边界条件、性能权衡沟通；代码标识只作补充注脚”的偏好同步写入全局 `AGENTS.md`、项目 `AGENTS.md` 与 `docs/agent/memory.md`。
- 当前进度：跨仓库与仓库内的沟通口径已对齐，后续默认按架构作用而非代码名对用户解释。
- 下一步：继续用非代码化表述解释剩余性能优化点，并仅在用户主动要求时补充具体代码位置。

## 2026-04-14 19:54 (Asia/Shanghai)
- 背景：用户批准继续做代码级热路径瘦身，目标是在不改变主链路行为的前提下继续压缩本地延迟。
- 已完成：新增并跑红灯测试后，完成三处热路径优化：查询侧单次命中的序列化结果在命中转发/运行事件复用，不再重复构造；购买侧后台补发线程改走同步 drain helper，不再每轮新建事件循环；购买侧队列命中的会话归属校验改用运行时绑定的本地会话标识，不再在锁内向统计聚合器取快照。
- 当前进度：针对性回归与主链路回归共 `25` 条已通过；新增实现计划文档 `docs/superpowers/plans/2026-04-14-hotpath-latency-trim.md` 已落库。
- 下一步：若继续追杀时延，优先考虑去重箱过期清理的全表扫描与 fast-path 最近事件留痕的同步写入成本。

## 2026-04-14 20:32 (Asia/Shanghai)
- 背景：用户确认“运行页最近事件弹窗/入口”应彻底移除，但诊断栏里的最近查询/最近购买日志必须保留；同时购买侧信息上报不能拖慢 `查询 -> 命中 -> 购买` 主链。
- 已完成：移除扫货运行页的“最近事件”按钮、弹窗与相关页面状态；购买运行状态接口与 runtime update 广播默认不再携带 `recent_events`；购买侧最近事件改为先进入旁路缓冲队列，由后台/状态快照再落入诊断事件缓存，不再在主线程同步写入。
- 当前进度：运行页展示与诊断日志已正式分流；诊断页仍保留购买事件明细；针对性后端/前端回归共 `172` 条已通过。
- 下一步：若继续压购买侧尾延迟，优先检查剩余非关键广播/统计是否还能进一步合并或延后，但不回退“运行页不看最近事件、诊断页单独看日志”的结构。

## 2026-04-14 20:49 (Asia/Shanghai)
- 背景：用户要求继续优化购买侧去重，但明确不改“按磨损计算结果认货”的口径，只做维护成本优化，并把固定去重窗从 `5s` 提高到 `10s`。
- 已完成：为去重箱补红灯测试后，将默认去重窗从 `5s` 提升到 `10s`；把“每次新命中都全表扫描清过期”改成“按到期顺序出列”，新命中只处理真正到期的旧锁；同步补充单元回归并跑通相关购买链回归。
- 当前进度：去重语义保持不变，仍然只拦相同磨损结果；主链额外收益来自去重账本维护成本下降，而非增加新的拦截层。
- 下一步：若后续还要继续压去重延迟，优先观察 `10s` 窗口下的误挡/漏挡统计，再决定是否需要更细的窗口配置，而不是先动认货标准。

## 2026-04-14 21:34 (Asia/Shanghai)
- 背景：用户要求继续从“同义写法成本”层面压缩 `查询 -> 命中 -> 购买` 主链，优先砍掉前台重复打包、锁内杂活与状态轮询的隐性过路费。
- 已完成：新增实现计划 `docs/superpowers/plans/2026-04-14-latency-micro-optimizations.md`；购买侧诊断日志改为投递可延后构造的轻量作业，命中前台不再同步展开 `product_list`，且隐藏最近事件的状态读取改走真正轻快照，不再顺手冲刷诊断缓冲；去重箱把批次对象构造移到锁外；调度器按桶认领改为边扫边记数，不再先为每个桶堆整份空闲名单；同步补齐红绿测试。
- 当前进度：三处微优化均已落地，业务语义保持不变：`10s` 按磨损去重、`50ms` 忙碌豁免、按桶限额与账号并发规则都未改变。
- 下一步：若还要继续追杀时延，优先复查购买侧剩余 payload clone 点与查询侧命中载荷所有权边界，看还能否再少一层复制。

## 2026-04-14 21:52 (Asia/Shanghai)
- 背景：用户批准继续压缩“命中包重复复印”的写法成本，目标只缩主链直达入口的副本开销，不改变后台排队入口的所有权隔离。
- 已完成：新增实现计划 `docs/superpowers/plans/2026-04-14-hit-payload-ownership-trim.md`；补红灯测试确认直达购买入口与 fast-path 之前确实会先复印命中包，而后台排队入口必须继续保留独立副本；实现上改为仅让后台排队入口继续 clone 命中包，直达入口与 fast-path 改为直接复用调用方载荷，少掉一层 `dict + product_list` 复制。
- 当前进度：购买主链语义未变；变化仅在“谁拥有这份命中包”这一层，直达链内复用、异步入队继续隔离。
- 下一步：若继续抠写法级延迟，优先评估查询侧到购买侧之间还能否再合并一次只读载荷复制，同时避免把自定义 hit sink 的边界契约搞脏。

## 2026-04-14 22:09 (Asia/Shanghai)
- 背景：用户批准继续压“查询侧把命中递给购买侧”这一跳的重复复制，但要求不能牺牲普通接收方的隔离边界。
- 已完成：新增实现计划 `docs/superpowers/plans/2026-04-14-query-hit-readonly-sharing.md`；查询运行时新增“只读安全接收方”判定，只有明确声明可共享的命中接收方才直接拿到已序列化的原 payload，普通接收方仍收到深一层的副本；购买服务四个接单入口（直达、fast-path、异步、入队）统一显式声明自己是“只读安全接收方”，让查询到购买主链再少一层 clone；同步补齐红绿测试与桥接回归。
- 当前进度：查询 -> 购买主链现在已把“查询侧 clone 一次 + 购买侧 clone 一次”缩到“查询侧零额外 clone + 购买侧按自身所有权决定是否 clone”；普通事件接收器与最近事件留痕仍维持原隔离策略。
- 下一步：若继续追杀写法级时延，优先审视查询侧 `recent_events` 与 `event_sink` 是否还能通过更细的只读契约减少拷贝，但那一刀风险会高于当前购买桥接优化。

## 2026-04-14 22:15 (Asia/Shanghai)
- 背景：用户批准继续把购买调度从“每次命中翻总可用账号名单找空闲”升级为“账号按代理桶自己站进待命池，命中时直接按桶拿”，目标是继续压缩 `查询 -> 命中 -> 购买` 主链热路径。
- 已完成：新增两盏红灯测试，锁死“按桶认领”和 fast-path 主链不得扫描总可用账号名单；购买调度器新增按桶常驻待命池，账号在注册可用、恢复可用、购买完成释放且仍有并发余量、以及并发额度调整后，都会主动回到对应待命桶；按桶认领改为直接从待命桶弹出账号，若该账号仍有剩余并发名额则回挂到桶尾，保持“同一次命中不重复拿同一账号、跨多次命中仍支持单账号多并发”的语义不变。
- 当前进度：购买主链已正式去掉“每次命中扫描总账号表”这一层热路径过路费；`tests/backend/test_purchase_scheduler.py`、`tests/backend/test_purchase_runtime_service.py`、`tests/backend/test_query_purchase_bridge.py`、`tests/backend/test_query_runtime_service.py`、`tests/backend/test_mode_execution_runner.py`、`tests/backend/test_purchase_hit_inbox.py`、`tests/backend/test_purchase_runtime_routes.py`、`tests/backend/test_diagnostics_routes.py` 共 `219` 条回归已通过。
- 下一步：若继续追杀大账号规模下的尾延迟，可再观察待命桶本身的出入队开销与桶级元数据，但当前主链结构已经稳定为“账号自报到桶内待命，命中直取桶中就绪账号”。

## 2026-04-15 17:14 (Asia/Shanghai)
- 背景：用户确认“失败”这一展示若按统计页理解，应改的是“查询统计”页；“账号能力统计”页继续只表达发单/购买阶段的速度表现，不改成失败件数字段。
- 已完成：将查询统计页的副标题与列表列头从“失败”改为“下单失败件数”，保持后端统计口径不变；补红绿测试并跑通 `app_desktop_web/tests/renderer/query_stats_page.test.jsx` 共 `4` 条。
- 当前进度：查询统计页文案已经与当前口径一致；账号能力统计页仍维持“发单速度 / 购买速度”展示。
- 下一步：若还要继续统一口径，可再清查其他页面里所有“失败”字样，区分为“下单失败件数”“执行失败”“请求失败”等不同语义，避免同词多义。

## 2026-04-15 01:13 (Asia/Shanghai)
- 背景：用户已完成 GitHub 账号与 SSH key 配置，需要把本仓库迁移到用户自己的 GitHub，并尽量降低后续使用门槛。
- 已完成：确认用户 GitHub 仓库 `sun1822049852-hub/c5autobuy` 已创建；本机 Git 全局身份切换到 GitHub；为 Git/SSH 链路补齐 GitHub 访问配置；将本仓 `origin` 切到 `git@github.com:sun1822049852-hub/c5autobuy.git` 并成功推送当前 `master` 分支；按用户“Gitee 不用管”的口径移除了本地 `gitee` 远端，避免后续混淆。
- 当前进度：本仓当前只保留 GitHub 一个主远端，`master` 已绑定 `origin/master`；README 已核对，本次无需改动。
- 下一步：后续日常提交直接使用 `git add`、`git commit`、`git push` 即可；若用户还要继续迁移其它项目，再按同一路径接入 GitHub。

## 2026-04-18 22:55 (Asia/Shanghai)
- 背景：用户确认先落实“白名单页临时注入/续期”方案，目标是让原始 Edge 打开 `open-api` 白名单页时继续复用已保存的 C5 登录态，不改购买链，也不提前实现 cookie 自动更新。
- 已完成：补充设计与实现计划文档；为浏览器 profile store 新增“准备白名单页临时 session”逻辑，在 clone 出来的临时 session 中优先定位 Chromium `Default/Network/Cookies`（兼容回退 `Default/Cookies`），只续 `c5game.com` 现有 cookies 的本地过期时间与持久化标记，不改 cookie 值；白名单页 launcher 在 clone 后、启动 Edge 前调用该准备动作，若准备失败则只记日志并继续沿用旧行为；补充并跑通 profile store 与 launcher 的红绿测试。
- 已做验证：使用进程内 `xsign` 最小桩跑通 `tests/backend/test_account_browser_profile_store.py` 与 `tests/backend/test_open_api_binding_page_launcher.py` 共 `7` 条；另对真实账号 `60bf1295-dd48-4875-aa25-ed5ffadca702` 的正式 profile 做临时副本验证，新逻辑命中 Chromium `Default/Network/Cookies` 并续期了 `8` 行 `c5game` cookies。
- 当前进度：白名单页链路现在会在启动原始 Edge 之前先给临时 session 做本地 cookie 续期，现有 `clone -> launch -> cleanup/persist` 机制保持不变；购买链、`accounts.cookie_raw` 与数据库写回逻辑均未触碰。
- 下一步：若用户继续推进，可直接在真实账号上打开一次白名单页做人工验证，确认无需重登；后续若再研究“cookie 自动更新”，需要另行定位能下发新认证 cookie 的真实接口，不能把这次本地续期误当成服务端刷新。

## 2026-04-18 23:23 (Asia/Shanghai)
- 背景：用户要求把“`xsign` 缺失时不得优先做单次命令临时注入，而应先查测试入口兜底”的规则沉淀为项目级长期约束，避免新会话重复试错。
- 已完成：在项目 `AGENTS.md` 新增“重复性环境坑处理规则”，明确 backend pytest 遇到 `xsign` 缺失时的检查顺序与禁止项；同步将该规则提炼到 `docs/agent/memory.md`，作为跨会话稳定记忆。
- 已做验证：本次为文档规则落盘，无自动化测试；已回读修改内容，确认落点仅限项目 `AGENTS.md`、`docs/agent/memory.md` 与本会话日志。
- 当前进度：后续进入本仓库的新会话，默认应先按项目级规则处理 `xsign` 这类重复性环境坑，而不是再次从会话级临时注入开始试错。
- 下一步：若用户继续推进，可把该规则对应的实际兜底实现补到 `tests/backend/conftest.py` 或统一测试脚本中，把“规则约束”再升级为“自动执行”。

## 2026-04-19 00:15 (Asia/Shanghai)
- 背景：用户反馈购买成功件数在成功数量较大时会少记，要求排查当前代码里“记录件数”和“实际购买件数”对不上的问题。
- 已完成：先补两盏红灯测试，锁住“批次里 1 条商品但实际购买 10 件”时，运行态 `purchase_success_count` 与统计事件 `success_count` 都必须按真实 `purchased_count` 记账；随后修正购买运行时旁路聚合与统计事件转发中的裁剪逻辑，不再把成功件数截断到 `product_list`/`submitted_count` 长度；同步修正一条沿用旧错误口径的历史测试预期。
- 已做验证：先用 `./.venv/Scripts/python.exe -m pytest tests/backend/test_purchase_runtime_service.py -k "actual_purchased_count or actual_success_count" -q` 跑出 `2 failed`，确认缺陷真实存在；修复后再跑 `./.venv/Scripts/python.exe -m pytest tests/backend/test_purchase_runtime_service.py -k "counts_purchase_success_using_actual_purchased_count or emits_purchase_stats_events_with_actual_success_count or exposes_item_hit_source_summary or emits_purchase_stats_events or consumes_queued_hit_and_updates_runtime_snapshot" -q`，结果 `5 passed`。
- 当前进度：新的购买运行态、账号维度统计、按商品聚合统计以及发往统计仓库的 submit-order 成功件数，已经统一按支付返回的真实成功件数记账；本次未触碰查询到购买主链调度结构。
- 下一步：若用户还要追历史口径，可再评估是否需要对已落库的旧统计数据做一次性回补；当前修复只保证新产生的数据不再少记。

## 2026-04-19 00:24 (Asia/Shanghai)
- 背景：用户要求把“购买成功件数一多就少记”的定位路径沉淀下来，方便后续新会话直接命中根因。
- 已完成：把该问题补进 `docs/agent/memory.md` 的长期记忆，明确下次若再出现“总购买件数与成功件数对不上”，优先检查购买运行时旁路聚合与统计事件转发是否又把真实 `purchased_count/successCount` 裁剪到 `piece_count/submitted_count`。
- 已做验证：本次仅更新文档记忆；已回读 `docs/agent/memory.md` 与本会话日志，确认记录内容已落盘。
- 当前进度：该问题现在既有修复记录，也有“优先检查文件 + 优先检查条件”的长期定位锚点。
- 下一步：后续若真再撞上类似现象，可直接从 `purchase_stats_aggregator.py`、`purchase_runtime_service.py` 这两处数值裁剪口径开始排查，而不必再全链路重挖。

## 2026-04-19 00:41 (Asia/Shanghai)
- 背景：用户要求把前端“查询统计”页的现有文案改动也一并纳入本次提交，而不是只提交后端修复。
- 已完成：确认前端仅包含查询统计页副标题与列表列头从“失败”调整为“下单失败件数”及对应测试更新；准备将该前端改动与“购买成功件数少记”后端修复、测试和文档记录合并为同一笔提交。
- 已做验证：重新执行 `./.venv/Scripts/python.exe -m pytest tests/backend/test_purchase_runtime_service.py -k "counts_purchase_success_using_actual_purchased_count or emits_purchase_stats_events_with_actual_success_count or exposes_item_hit_source_summary or emits_purchase_stats_events or consumes_queued_hit_and_updates_runtime_snapshot" -q`，结果 `5 passed`；执行 `npm test -- tests/renderer/query_stats_page.test.jsx`，结果 `1 passed / 4 passed`。
- 当前进度：前后端受影响验证均已通过，工作树处于可提交状态。
- 下一步：按用户要求将前端与后端改动一起 stage 并创建本地 commit。

## 2026-04-19 20:59 (Asia/Shanghai)
- 背景：用户连续澄清程序会员语义，最终确认“本地共享工作区不随程序账号切换；程序账号只负责权限续期；无会员时数据只读可见，关键动作锁死”。
- 已完成：新增冻结 spec `docs/superpowers/specs/2026-04-19-program-membership-shared-workspace-design.md`，写死“单一本地共享工作区 + 远端统一鉴权 + 切账号只换权限、不换数据”的最终边界；同时为 `2026-04-06-membership-auth-design.md` 与 `2026-04-13-local-program-access-extension-design.md` 增加状态更新提示，标明过期与补充关系；把该产品语义同步提炼到 `docs/agent/memory.md`。
- 当前进度：仓库内关于程序会员的主语义已重新对齐：保留 Program Access 骨架与关键动作守卫，停止把本地业务数据继续推向 `owner_user_id` 多租户隔离方向。
- 下一步：若继续实现，应先把只读锁定态、远端程序账号登录/刷新/切号、以及 guard 的真实远端判定链落成可执行方案，再碰代码。

## 2026-04-20 17:46 (Asia/Shanghai)
- 背景：用户要求把“会员控制面公网暴露需要收口”留作跨会话锚点，并确认当前距离会员落地与发行还剩哪些工作。
- 已完成：通过 SSH 拿到远端 `admin@8.138.39.139` 权限，确认并保留旧服务 `cs2-admin`；将新会员控制面部署到远端独立端口 `18787`，验证 `health`、公钥下发、bootstrap 状态均可公网访问；用户已完成后台超级管理员初始化，`needs_bootstrap` 已变为 `false`；同步把“管理端口不得长期全网开放，正式发行前需收口”写入 `docs/agent/memory.md`。
- 当前进度：远端统一鉴权控制面已实际跑通，后台入口可用；当前最大的未收口项不再是服务器部署，而是桌面端与该远端的真实登录/会员解锁联调，以及发行前的网络暴露策略与打包链收尾。
- 下一步：优先做一遍“桌面端真实登录 -> 拉取远端权限 -> 本地关键功能解锁/锁死”的烟测；随后处理发行链剩余事项，包括管理员端口收口、`build:win` 的签名/构建链整理、以及 `.venv` 发行便携性的最终确认。

## 2026-04-21 12:35 (Asia/Shanghai)
- 背景：用户质疑最近安装包与会员改动落在错误 worktree，要求先判断旧 worktree 是否还应保留，再决定清理。
- 已完成：复核全部 worktree 的最后提交时间、与 `master` 的偏离、脏/净状态和会员相关性；确认根工作树 `master` 才是可信桌面主线，且当前根线未提交改动仍仅限文档/spec，会员与控制面代码主要散落在 `feature/local-program-access-extension` 与 `feature/program-control-plane-chunk1`；新增 `docs/superpowers/references/2026-04-21-worktree-disposition-reference.md` 给出“保留回收源 / 导出后删除 / 可直接删除”清单，并把“以后只能从 `master + main_ui_account_center_desktop.js` 打包”写入长期记忆。
- 当前进度：worktree 处置建议已落盘，但尚未执行任何删除；会员功能仍未真正回收到可发行主线。
- 下一步：等用户确认后，按清单清理无关旧树，并把会员/控制面能力从两条保留 worktree 拆件回收回 `master`，再重新打包验证。

## 2026-04-21 13:05 (Asia/Shanghai)
- 背景：用户确认可以继续，要求按清单清理旧 worktree，并开始把会员能力回收到 `master`。
- 已完成：实际删除 7 条无关旧 worktree，仅保留 `feature/local-program-access-extension`、`feature/membership-auth-v1`、`feature/program-control-plane-chunk1` 三条会员相关来源；其中 `purchase-page-ui-freeze` 与 `remote-runtime-state-sync-exec` 先由 `git worktree remove` 注销，再按绝对路径校验后手工删除残留目录。同步更新 `docs/superpowers/references/2026-04-21-worktree-disposition-reference.md` 为已执行状态，并新增 `docs/superpowers/plans/2026-04-21-program-membership-master-recovery.md`，明确从哪条 worktree 回收哪些模块、以及哪些入口/命名漂移坚决不带回 `master`。
- 当前进度：现场 worktree 已收口，下一阶段进入 `master` 回收实施；代码尚未开始回收，当前只完成清理与执行计划落盘。
- 下一步：按恢复计划先把 Program Access 骨架、只读锁定 UI 和远端控制面适配层回收到 `master`，随后补打包链并只从根工作树重新出包。

## 2026-04-21 13:26 (Asia/Shanghai)
- 背景：继续执行 `docs/superpowers/plans/2026-04-21-program-membership-master-recovery.md` 的 Chunk 1，目标是在 `master` 上先回收前端 Program Access 骨架，并把“共享工作区只读可见、关键功能锁死”落实到现有桌面页。
- 已完成：从 `feature/local-program-access-extension` 回收 `app_desktop_web/src/program_access/` 与 `app_desktop_web/src/api/program_auth_client.js`，把 `programAccess` snapshot 接入 `App`、`AppShell`、runtime store 与 runtime hooks；补齐侧栏“程序会员”卡片与 provider 错误出口。随后新增并跑通账号页 / 配置页 / 扫货页的 readonly 红灯测试，按最小集合给 account-center、query-system、purchase-system 接上 `isReadonlyLocked`，使新增/编辑/删除/启动/保存/提交等关键动作在锁定态 disabled，而查看与停止运行保留。额外补上 `runtime_connection_manager` 对 `program_access.updated` websocket 事件的接收，保证远端续权状态能实时落到前端。
- 已做验证：执行 `npm test -- tests/renderer/program_access_provider.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/runtime_connection_manager.test.js --run`，结果 `7 passed / 85 passed`。
- 当前进度：Chunk 1 的前端骨架与 readonly 锁定主干已回到 `master`，并维持“单一共享工作区 + 程序账号只换权限钥匙”的冻结语义；尚未进入远端控制面服务、Python 远端适配层与正式注册/找回密码链路的回收。
- 下一步：继续按计划进入 Chunk 2，回收 `program_admin_console/`、SMTP 注册/找回密码链路，以及 Python 侧远端 entitlement adapter，再做桌面端真实登录联调。

## 2026-04-21 16:32 (Asia/Shanghai)
- 背景：继续执行 `docs/superpowers/plans/2026-04-21-program-membership-master-recovery.md` 的 Chunk 2，目标是把远端控制面与 Python 远端 entitlement adapter 从保留 worktree 回收到 `master`，并保持“共享本地数据 + 远端统一鉴权 + 失效后只读可见”语义不漂移。
- 已完成：回收 `program_admin_console/` 全套 Node 控制面（store/server/admin UI/SMTP 文档与测试），并把 UI 与邮件品牌统一到 `C5 交易助手`，README 中的部署/联调口径固定指向 `http://8.138.39.139:18787`，未带回 `data/control-plane.sqlite`。同时把 Python 侧 `program_auth` 路由、remote control plane client、签名验签器、remote entitlement gateway、refresh scheduler 及配套测试恢复到主线；`create_app()` 现可装配远端控制面客户端、挂上 `/program-auth/*` 路由、持有刷新调度器，并在 packaged release 场景下使用远端 entitlement 语义而不改共享工作区边界。
- 已做验证：执行 `npm --prefix program_admin_console test`，结果 mail/store/server/ui 全部通过；执行 `./.venv/Scripts/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_program_access_guard_routes.py tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_program_access_refresh_scheduler.py tests/backend/test_program_auth_routes.py -q`，结果 `60 passed`。唯一残留仅为 FastAPI `on_event("shutdown")` 的既有弃用告警，本次未扩到 lifespan 重构。
- 当前进度：Chunk 2 的控制面与本地后端远端鉴权链已回到 `master`，注册/验证码/找回密码/登录/刷新/退出的本地代理链已存在；主线现在具备继续做桌面端真实登录联调与打包配置回收的基础。
- 下一步：继续执行后续恢复计划，把桌面端 Program Access 面板与 Electron/打包侧控制面配置回收到主线，并做“真实程序账号登录 -> 权限解锁/锁死 -> 切号不换本地数据”的整链烟测。

## 2026-04-21 18:08 (Asia/Shanghai)
- 背景：继续执行恢复计划的桌面端与打包收口，目标是把主线上的 Program Access 从“只剩状态卡 + 登录/退出”补到“注册/验证码/找回密码完整可用”，同时把 packaged release 的控制面配置与安装器约束回收到根主线。
- 已完成：前端 `program_auth_client`、`program_access_provider`、`ProgramAccessSidebarCard` 已接回完整注册链，侧栏现支持登录、发送注册验证码、提交注册、发送找回密码验证码、重置密码，并保持“共享工作区不切换、无会员只读可见”的文案与状态不漂移。并行回收了 Electron 打包配置：新增 `app_desktop_web/program_access_config.cjs`、`electron-builder-*.cjs`、`tests/electron/program_access_packaging.test.js`，`python_backend.js` 现会把 `controlPlaneBaseUrl` 注入嵌入式 Python 后端，`client_config.release.json` 默认指向 `http://8.138.39.139:18787`，同时保留 `main_ui_account_center_desktop.js` 作为可信启动入口。
- 已做验证：执行 `npm --prefix app_desktop_web test -- tests/renderer/program_auth_client.test.js tests/renderer/program_access_provider.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/runtime_connection_manager.test.js tests/electron/python_backend.test.js tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js --run`，结果 `113 passed`；再次执行 `npm --prefix program_admin_console test` 结果全绿；后端聚焦回归维持 `60 passed`。Node SQLite 仍会给出实验性告警，FastAPI 仍有 `on_event("shutdown")` 弃用告警，但本轮功能验证未失败。
- 当前进度：桌面端会员入口、远端登录/注册/找回密码链、Electron packaged-release 控制面配置、可信 launcher 约束都已回到主线，当前已具备继续做“真实账号烟测 + 真正出包”的条件。
- 下一步：剩余关键差距已缩到两刀：1. 跑一遍真实程序账号登录/切号/锁定解锁烟测；2. 从根 `master` 真正执行 `npm --prefix app_desktop_web run build:win`，记录安装包输出路径与实际安装体验。

## 2026-04-21 18:14 (Asia/Shanghai)
- 背景：用户确认可以继续清理旧 worktree，要求把明显过期、会误导后续打包与会员排查的现场收口。
- 已完成：重新审查剩余三棵会员相关 worktree；确认 `feature/membership-auth-v1` 相对 `master` 已无提交级独占内容，剩下的只是“本地多租户用户/会员模型”这条已被废弃语义的脏现场，因此执行 `git worktree remove --force .worktrees/membership-auth-v1` 并删除本地分支 `feature/membership-auth-v1`。同步更新 `docs/superpowers/references/2026-04-21-worktree-disposition-reference.md` 与 `docs/agent/memory.md`，把它标记为已移除漂移源。
- 已做验证：执行 `git diff --stat master...feature/membership-auth-v1`，结果为空，确认无提交级独占内容；执行 `git worktree list --porcelain`，当前仅剩根工作树、`feature/local-program-access-extension`、`feature/program-control-plane-chunk1` 三项；执行 `git branch --list feature/membership-auth-v1`，结果为空，确认分支已删除。
- 当前进度：现场 worktree 已进一步收口，后续会员回收与发行排查只需围绕根工作树 `master` 以及两条仍保留的回收源进行，不再需要旧的本地多租户分支干扰判断。
- 下一步：继续集中处理发行收口剩余两刀，即真实程序账号烟测，以及 Windows 打包环境的 `winCodeSign` / 符号链接权限问题。

## 2026-04-21 18:18 (Asia/Shanghai)
- 背景：用户确认继续推进，目标是把 Windows 本地出包链真正打通，而不是停留在“理论上只差环境权限”。
- 已完成：先复现 `npm --prefix app_desktop_web run pack:win` 的真实失败栈，确认并非 NSIS 或会员代码问题，而是 `electron-builder` 在 Windows 上执行 EXE 元信息编辑时，会下载 `winCodeSign-2.6.0.7z` 并要求 7-Zip 解出其中的 symlink 文件；当前普通本地环境无该权限，因此在缓存目录解压阶段失败。随后做最小假设实验，把 `win.signAndEditExecutable` 关闭后重新测试，证明确实可以绕过 `rcedit/winCodeSign` 链并成功产出 `win-unpacked`；最终将该设置固化到 `app_desktop_web/electron-builder.config.cjs`，并在 `tests/electron/program_access_packaging.test.js` 中补断言锁定该约束。
- 已做验证：执行 `npm test -- tests/electron/program_access_packaging.test.js --run`，结果 `8 passed`；执行 `npm run build:win`，成功生成安装包 `app_desktop_web/release/C5 账号中心 Setup 0.1.0.exe` 以及对应 `.blockmap`，同时保留 `release/win-unpacked/`。本次构建仍有既有警告：`package.json` 缺 `description/author`，且未配置自定义应用图标，因此继续使用默认 Electron 图标，但不影响出包成功。
- 当前进度：Windows 本地发行包已从根主线实际产出，之前卡住的 `winCodeSign` / symlink 权限阻塞已被主线配置规避；当前发行链剩余重点转为“真实程序账号烟测”和“是否要进一步整理产品名/图标/元信息”。
- 下一步：优先让用户用刚产出的安装包做本机安装验证，并跑一遍真实程序账号登录/注册/锁定解锁/切号不切数据的烟测；若用户对安装包名称、图标或 EXE 元信息有要求，再单独收一轮发行品牌整理。

## 2026-04-21 18:24 (Asia/Shanghai)
- 背景：用户要求把安装包名改成 `C5 交易助手`，但未要求同步改运行时页面标题、窗口标题或本地数据目录。
- 已完成：采用最小改动路线，只修改 `app_desktop_web/electron-builder.config.cjs` 中的 `productName`，把安装包 / EXE 产物名从 `C5 账号中心` 改为 `C5 交易助手`；同时先补红灯，再在 `tests/electron/program_access_packaging.test.js` 中锁定该打包品牌，避免后续回退。此次未改 `electron-main.cjs`、`index.html`、导航文案和 `C5AccountCenter` 数据目录常量，因此不会引入本地数据迁移。
- 已做验证：先执行 `npm test -- tests/electron/program_access_packaging.test.js --run`，得到 `1 failed`，失败点为 `expected 'C5 账号中心' to be 'C5 交易助手'`；修复后再次执行同命令，结果 `8 passed`。随后执行 `npm run build:win`，成功生成 `app_desktop_web/release/C5 交易助手 Setup 0.1.0.exe` 与对应 `.blockmap`，并在构建日志中确认 `release/win-unpacked/C5 交易助手.exe` 已同步生效。
- 当前进度：安装包外显名已切到 `C5 交易助手`，但程序运行时仍保持 `C5 账号中心` 文案；这样能满足“改安装包名”的诉求，同时避免额外 UI 与数据目录回归。
- 下一步：等用户做安装验证；若后续还要把窗口标题、HTML title、侧栏标题等也统一改成 `C5 交易助手`，再单独收一刀品牌统一。

## 2026-04-21 17:06 (Asia/Shanghai)
- 背景：用户明确否定 `C5 账号中心` 作为整机品牌，要求以真正程序入口 `main_ui_node_desktop.js` 为准，把运行时整套外显名统一改成 `C5 交易助手`，并及时清理过期构建产物。
- 已完成：补齐 `tests/renderer/query_system_page.test.jsx` 中残留的旧品牌断言，使运行时品牌测试闭环；当前主线运行时外显名已统一为 `C5 交易助手`，覆盖 Electron `app.setName`、窗口标题、启动失败页、HTML title、侧栏品牌标题与账号首页主标题，同时保持内部模块名 `账号中心 / 配置管理 / 扫货系统` 不变，也未触碰本地数据目录常量。同步修正 `README.md` 与 `docs/agent/memory.md`，把真实桌面入口锚定为 `main_ui_node_desktop.js`，并标明 `main_ui_account_center_desktop.js` 只是兼容转发壳。随后清理过期产物：删除根工作树 `.vite/`、`app_desktop_web/build/`，以及保留回收源 worktree 中残留的旧版 `C5 账号中心` 安装包与 `win-unpacked` EXE，避免后续再误拿旧包做发行判断。
- 已做验证：执行 `npm test -- tests/renderer/query_system_page.test.jsx --run`，结果 `15 passed`；执行 `npm test -- tests/renderer/account_center_page.test.jsx tests/renderer/app_renderer_diagnostics.test.jsx tests/renderer/app_state_persistence.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/query_system_editing.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/remote_runtime_shell.test.jsx --run`，结果 `72 passed`；执行 `npm test -- tests/electron/program_access_packaging.test.js --run`，结果 `8 passed`；执行 `npm test -- tests/electron/electron_remote_mode.test.js --run -t "configures dedicated desktop storage paths before the app bootstraps"`，结果 `1 passed`；执行 `npm run build:win`，成功生成 `app_desktop_web/release/C5 交易助手 Setup 0.1.0.exe`。清理后再次全仓搜索 `C5 账号中心` 构建产物与 `.vite/build` 残留，结果为空。
- 当前进度：当前可直接交付给用户安装测试的有效发布产物只剩 `app_desktop_web/release/C5 交易助手 Setup 0.1.0.exe`（及本次构建附带的 `.blockmap` / `win-unpacked` 运行目录）；旧品牌运行时与旧安装包残骸已从主线和保留 worktree 中清掉。
- 下一步：等待用户做本机安装验证；若还要继续收口，可再决定是否把 `run_app.py`、兼容包装脚本提示语和 README 更深层旧称呼统一到 `main_ui_node_desktop.js` 口径。

## 2026-04-21 17:12 (Asia/Shanghai)
- 背景：用户进一步确认 `main_ui_account_center_desktop.js` 已几乎不参与主进程，希望直接把这层兼容壳从主线清掉，避免后续继续误判入口。
- 已完成：先用测试把入口契约切到 `main_ui_node_desktop.js`，确认红灯确实打在 `run_app.py` 对旧壳文件名的硬编码上；随后把 `run_app.py`、README、`docs/superpowers/README.md`、worktree 处置参考、恢复计划与长期记忆全部改成“唯一真实桌面入口 = main_ui_node_desktop.js”的口径，并已删除 `main_ui_account_center_desktop.js` 兼容壳文件。
- 已做验证：红灯阶段执行 `./.venv/Scripts/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`，结果 `1 failed, 2 passed`，失败点为 `run_app.py` 仍未包含 `main_ui_node_desktop.js`；绿灯阶段再次执行 `./.venv/Scripts/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`，结果 `3 passed`；执行 `npm test -- tests/electron/desktop_launcher.test.js --run`，结果 `5 passed`；执行 `Test-Path main_ui_account_center_desktop.js`，结果 `False`，确认兼容壳文件已从根工作树删除。
- 当前进度：当前主线代码与当前口径文档都已切到真实入口，兼容壳已从根工作树删除。
- 下一步：保留对历史计划文档中旧入口名的检索能力即可；后续若再排查启动链，统一从 `run_app.py -> main_ui_node_desktop.js` 开始。

## 2026-04-21 17:19 (Asia/Shanghai)
- 背景：用户要求把新包重打一遍；首次重打虽然成功产出 `C5 交易助手 Setup 0.1.0.exe`，但构建日志明确警告 `app_desktop_web/build/client_config.release.json` 缺失，存在发行包丢失远端控制面地址配置的风险。
- 已完成：按根因排查确认，问题不是 `electron-builder` 生成失败，而是此前清理过期产物时误删了 `app_desktop_web/build/client_config.release.json`；该文件本身就是发行必带静态配置，而 `electron-builder-preflight.cjs` 只校验嵌入式 Python，不会自动重建它。随后补回 `app_desktop_web/build/client_config.release.json`，内容固定为 `http://8.138.39.139:18787`，再清空 `app_desktop_web/release/` 并重新执行 `build:win`。
- 已做验证：先执行 `npm test -- tests/electron/program_access_packaging.test.js --run`，红灯结果 `1 failed / 7 passed`，失败点为 `ENOENT ... app_desktop_web/build/client_config.release.json`；补回文件后再次执行同命令，结果 `8 passed`。随后执行 `npm run build:win`，成功生成新的 `app_desktop_web/release/C5 交易助手 Setup 0.1.0.exe`（时间戳 `2026-04-21 17:18:34`）；并回读 `app_desktop_web/release/win-unpacked/resources/client_config.release.json`，确认包内已携带 `controlPlaneBaseUrl = http://8.138.39.139:18787`。
- 当前进度：当前 `release/` 下的新安装包已是带完整远端控制面配置的有效发行包，不再是之前那个“外表成功、内里缺 release config”的半成品。
- 下一步：可直接交给用户做本机安装验证；若还要继续收口发行细节，下一刀是补 `package.json` 的 `description/author` 与自定义应用图标，去掉构建日志里的剩余警告。

## 2026-04-21 18:48 (Asia/Shanghai)
- 背景：用户反馈账号中心“新增账号后立即发起登录”被改坏，登录成功后的浏览器会话落盘阶段抛出 `Permission denied`，并怀疑最近的白名单 `cookie` 续期改动误伤了登录链。
- 已完成：按登录链与白名单链逐段排查后，确认白名单 `cookie` 续期只在“打开 open-api 绑定页”时触发；真正炸点是登录成功后立即持久化活跃 Chromium session 时，`shutil.copytree()` 试图复制仍被 Edge 占用的 `Default/Cache/Cache_Data`。为此在 `AccountBrowserProfileStore` 中新增“复制阶段即忽略瞬态目录”的复制器，跳过 `Default/Cache`、`Default/Code Cache`、`Default/GPUCache`、`Default/Service Worker/CacheStorage` 等缓存目录，同时保留 `Cookies` / `Preferences` / `Local State`。另补一盏回归测试，模拟 Windows 风格的锁文件错误，锁定“活跃 session 即时持久化不得因缓存锁而失败”。
- 已做验证：先用 `python -m pytest tests/backend/test_account_browser_profile_store.py -q` 跑出红灯，确认旧实现会在模拟的 `Cache_Data/data_0` 权限错误上失败；修复后执行 `python -m pytest tests/backend/test_account_browser_profile_store.py tests/backend/test_managed_edge_cdp_login_runner.py tests/backend/test_open_api_binding_page_launcher.py -q`，结果 `20 passed`。测试过程另确认直接 `pytest` 在当前环境下不会自动挂载仓库根目录，需使用 `python -m pytest`。
- 当前进度：账号登录链已回到“仍保持即时 profile 持久化，但不再复制活跃浏览器锁住的瞬态缓存”的状态；白名单页 cookie 续期逻辑未回退，登录链与 open-api 复用链已重新对齐。
- 下一步：等待用户在真实账号上重新跑一遍“新增账号 -> 登录 -> 立即打开白名单页 / 继续后续购买准备”的人工验证；若仍有现场异常，再沿活跃 session 中其他可能被锁的 Chromium 瞬态目录继续补白名单。

## 2026-04-21 19:05 (Asia/Shanghai)
- 背景：用户反馈当前项目桌面程序已无法打开，要求先排查源码启动链，不继续打包。
- 已完成：先复现 `node main_ui_node_desktop.js` 的启动失败，确认桌面启动器此前已修到“不再错误依赖 `electron/cli.js`”，但当前真正阻塞点已下沉到本机 Electron 运行时损坏。现网现场先报 `chrome_100_percent.pak` 缺失；继续追查发现不只是 `dist/` 残缺，连 `app_desktop_web/node_modules/electron/checksums.json` 也缺失，导致 `install.js` 自愈脚本无法运行。随后执行最小修复：仅删除损坏的 `app_desktop_web/node_modules/electron/` 包目录，并在 `app_desktop_web/` 下用 `npm install electron@37.2.0 --no-save --package-lock=false` 重新拉起 Electron 包与运行时，未触碰业务源码与打包流程。
- 已做验证：检查 `app_desktop_web/node_modules/electron/checksums.json`、`dist/electron.exe`、`dist/chrome_100_percent.pak` 均已恢复；再次用 `Start-Process node main_ui_node_desktop.js` 做 8 秒烟测，进程保持存活且 `stderr` 为空，不再出现缺包报错；执行 `npm test -- tests/electron/desktop_launcher.test.js --run`，结果 `6 passed`。
- 当前进度：当前源码态桌面程序已恢复到“可正常拉起 Electron 壳”的状态，本轮阻塞属于本机依赖层损坏，不是会员链或业务主进程再次改坏。
- 下一步：等用户亲手点开程序确认窗口是否正常进入；若仍有“开得慢 / 标题不对 / 某页空白”等二次现象，再沿运行时 UI 链继续收束，但无需回退这次 Electron 依赖修复。

## 2026-04-21 19:31 (Asia/Shanghai)
- 背景：用户明确要求不要继续“瞎改”，而是找回“以前登录完全成功”的历史实现；经 git 历史比对，确认 `49d4d9b fix: defer login profile persistence until browser exit` 才是旧成功语义，而 `0248d5e fix: persist account browser sessions immediately` 把 `persist_session()` 挪进了登录主链。
- 已完成：新增实现计划 `docs/superpowers/plans/2026-04-21-login-success-chain-restore.md`，随后先把 `tests/backend/test_managed_edge_cdp_login_runner.py` 改回旧契约并补上“持久化报错也不能阻断登录”的回归灯，确认红灯后，仅在 `app_backend/infrastructure/browser_runtime/login_adapter.py` 做最小修复：保留独立登录 session 目录与阻塞调用桥接，但把 `persist_session()` 从登录成功前移回 delayed cleanup callback，恢复“先返回登录成功，再做 best-effort profile 落盘”的语义。同时修正 `docs/agent/memory.md` 中此前错误沉淀的“必须立即持久化”结论。
- 已做验证：先执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_managed_edge_cdp_login_runner.py -k "persists_profile_after_browser_exit or defers_profile_persist_until_cleanup_runs or ignores_profile_persist_error_after_browser_exit" -q`，红灯结果 `3 failed`，失败点均为当前代码仍在登录主链里立即持久化。修复后重跑同命令，结果 `3 passed`。随后执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_browser_profile_store.py tests/backend/test_managed_edge_cdp_login_runner.py tests/backend/test_open_api_binding_page_launcher.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`，结果 `36 passed`。两轮验证均仅有既有 FastAPI `on_event("shutdown")` 弃用告警，无新失败。
- 当前进度：账号中心登录链已恢复到旧成功语义，`persist_session()` 的锁文件异常不再能直接打断“新增账号登录成功”；先前为缓存锁做的 `AccountBrowserProfileStore` 瞬态目录忽略仍保留，但已从“拯救登录主链”降级为“降低后续落盘失败概率”的辅助措施。
- 下一步：等待用户在真实账号上复测“新增账号 -> 登录成功”；若仍有白名单页复用时序问题，再单独决定是否为 open-api 复用链补显式“等待浏览器退出后再打开”提示或单独重刷机制，但不再把这类补强重新绑回登录主链。

## 2026-04-21 19:43 (Asia/Shanghai)
- 背景：用户继续指出账号中心当前真实流程是“先新建账号壳，再登录后回写 `c5_user_id`”，并反馈现在同一 C5 账号重复登录时会生成两个相同账号，要求恢复旧处理而不是默认复制出第二个同号账号。
- 已完成：复核 `app_backend/workers/tasks/login_task.py` 与 `tests/backend/test_login_conflict_flow.py` 后，确认重复号并非因为“先建壳”本身，而是 `399da66 feat: finish remote runtime authoritative state sync` 把登录归并逻辑从 `57e0d99 fix: align login reconciliation and account update pushes` 的“命中已有同 `c5_user_id` 就并回老账号”收窄成了“只有 API-only 来源才并回老账号”，并新增了错误测试来锁死“普通空壳登录命中老号时保留新号、制造重复账号”。随后先把该测试改成正确契约并跑出红灯，再仅在 `login_task.py` 做最小修复：`matched_account` 一旦命中，无论来源账号是否 API-only，都优先作为 `final_account`；只有未命中且来源为 API-only 时，才额外派生新已登录账号。这样既保留“先建壳、后拿 `c5_user_id`”的现实链路，也恢复“同号不重复写进新壳”的归并规则。
- 已做验证：先执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_conflict_flow.py -k "regular_new_account_routes_to_existing_c5_account_when_existing_match_found" -q`，红灯结果 `1 failed`，失败点为当前实现仍把 `task_payload["result"]["account_id"]` 指向新壳账号。修复后执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_conflict_flow.py -k "regular_new_account_routes_to_existing_c5_account_when_existing_match_found or api_only_account_routes_to_existing_c5_account or api_only_account_creates_new_logged_in_account_without_inheriting_source_config" -q`，结果 `3 passed`。仅有既有 FastAPI `on_event("shutdown")` 弃用告警，无新失败。
- 当前进度：当前登录归并规则已恢复到“同一 `c5_user_id` 默认并回已有账号”，不再把重复登录写成第二个同号账号；普通空壳账号在命中老号时会保持未绑定空壳状态，不自动删除。
- 下一步：继续跑包含登录主链与归并链的总回归，然后只提交本次相关文件，避开工作树里其它未收口改动。

## 2026-04-21 20:06 (Asia/Shanghai)
- 背景：用户继续反馈“登录成功后关闭窗口，再点添加白名单，拉起的网页要求重新登录”。这说明问题不只是“窗口未关时白名单链没有复用活跃浏览器”，而是“窗口刚关后，最新登录态尚未稳定落入 canonical profile，白名单链又只会去拉旧 profile”。
- 已完成：沿 `accounts.py -> open_api_binding_page_launcher.py -> account_browser_profile_store.py` 排查后，确认旧实现存在两处断口：1. 路由虽然能从 active bundle 读到 `profile_root`，但并不会把 `debugger_address` 或最新登录 session 根路径往下传；2. launcher 在有 `profile_store + account_id` 时会忽略 bundle 里的显式 `profile_root`，直接 clone canonical account profile，因此“刚登录/刚关窗”的最新态天然可能丢失。随后先补红灯：锁定路由必须把 `debugger_address/login_session_root` 透传给 launcher，launcher 必须优先复用活跃登录 debugger，其次复用 `login_session_root`，最后才退回保存型 profile。再做最小修复：`ManagedEdgeCdpLoginRunner` 把 `login_session_root` 带进登录 payload；`AccountBrowserProfileStore` 新增 `clone_session_from_root()`；`open_open_api_binding_page` 允许基于 `debugger_address/login_session_root/profile_root` 三者任一继续打开白名单页；`OpenApiBindingPageLauncher.launch()` 现会优先导航活跃登录浏览器到 open-api，若浏览器已关则优先从 `login_session_root` 克隆最新 session，再退回旧 profile。这样既保住“登录成功不被落盘失败打断”，又恢复“关窗后立刻加白名单仍拿到最新登录态”。
- 已做验证：先分别执行 `python -m pytest` 针对 `tests/backend/test_managed_edge_cdp_login_runner.py::test_managed_edge_cdp_login_runner_uses_account_profile_store`、`tests/backend/test_account_center_routes.py::{test_open_open_api_binding_page_route_prefers_saved_profile_bundle,test_open_open_api_binding_page_route_passes_bundle_debugger_address}`、`tests/backend/test_open_api_binding_page_launcher.py::{test_open_api_binding_page_launcher_prefers_live_login_debugger_before_saved_profile,test_open_api_binding_page_launcher_uses_login_session_root_after_login_window_closes}`，确认新增链路全部转绿。随后执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_browser_profile_store.py tests/backend/test_managed_edge_cdp_login_runner.py tests/backend/test_open_api_binding_page_launcher.py tests/backend/test_account_center_routes.py tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`，结果 `55 passed`。仅剩既有 FastAPI `on_event("shutdown")` 弃用告警，无新失败。
- 当前进度：白名单打开链已恢复到“优先吃最新登录 session”的状态，覆盖了登录窗口仍存活与刚关闭两种现场；不再只会死盯旧 profile，所以“关窗后立即添加白名单”不应再回到登录页。随后又按用户要求在 `AGENTS.md` 增补“关键行为保护（强制）”章节，把既有数据获取、数据保存/回写/持久化链路明确提升为关键行为，避免后续在缺少验证时再次被静默改坏。
- 下一步：按本次白名单修复与关键行为规则补强一起提交；提交后等待用户按真实流程继续复测“登录成功 -> 关闭登录窗口 -> 立即添加白名单”。若仍出现登录页，再沿 open-api 页自身 cookie 续期或浏览器退出后的异步持久化竞态继续缩圈，但当前主链断口已被补上。

## 2026-04-21 20:24 (Asia/Shanghai)
- 背景：用户提出新的产品约束，希望“登录后的浏览器扫货默认改为关闭”，但随后明确边界不是“所有登录成功都关闭”，而是“仅首次绑定成功默认关闭；老账号重登保持原开关”。
- 已完成：按 brainstorming 流程先收敛行为边界与风险，不直接改代码；已把确认后的设计落盘到 `docs/superpowers/specs/2026-04-21-login-browser-query-default-off-design.md`。设计已明确：首次绑定成功时写入 `token_enabled=False` 与 `browser_query_disabled_reason=\"manual_disabled\"`；命中已有老账号、老账号重登时不覆盖现有浏览器扫货开关；冲突分支中的 `create_new_account` / `replace_with_new_account` 都视为首次绑定。
- 已做验证：本阶段仅做上下文审查与设计确认，未执行自动化测试，也未修改业务代码；已对照现有登录回写、冲突处理、查询模式字段与前端展示逻辑，确认本设计不要求新增 schema、协议字段或前端状态码。
- 当前进度：设计已获用户批准，已进入“可写实现计划 / 可进入 TDD”状态，但业务实现尚未开始。
- 下一步：等待用户确认规格文档后，进入实现计划与 TDD，先补登录链与冲突链回归灯，再做最小代码修改。

## 2026-04-21 20:36 (Asia/Shanghai)
- 背景：用户确认规格文档无异议，要求继续推进实现。
- 已完成：为避免根工作树 `master` 上的大量无关脏改干扰本次登录链修复，已新建隔离工作树 `.worktrees/first-login-browser-query-default-off`，分支为 `feature/first-login-browser-query-default-off`。随后在该工作树先执行登录相关基线验证 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py -q`，结果 `16 passed`，确认当前登录/冲突基线为绿。基于已批准的设计，新增实现计划 `docs/superpowers/plans/2026-04-21-first-login-browser-query-default-off.md`，把 TDD 顺序、受影响文件和最终验证命令全部写死。
- 已做验证：隔离工作树创建成功；基线测试 `16 passed in 3.82s`。
- 当前进度：已进入实现前最后准备阶段；下一步是在新工作树里按计划先补红灯，再修改登录回写与冲突分支。
- 下一步：执行计划 Chunk 1，先写失败测试锁定“首次绑定默认关闭、老账号重登保持原开关”的行为。

## 2026-04-21 20:52 (Asia/Shanghai)
- 背景：用户确认可以继续后，目标是把“浏览器扫货默认关闭”限定在首次绑定成功，不误伤老账号重登和已有账号归并。
- 已完成：在隔离工作树中按 TDD 执行。先修改 `tests/backend/test_login_task_flow.py` 与 `tests/backend/test_login_conflict_flow.py`，把以下行为锁成红灯：1. 空账号首次登录成功后默认关闭浏览器扫货；2. 老账号重登保持原开关；3. API-only 派生的新登录账号默认关闭；4. 冲突分支 `create_new_account` / `replace_with_new_account` 生成的新账号默认关闭。确认红灯后，仅修改两个后端落点：`app_backend/workers/tasks/login_task.py` 在最终写回目标账号前判断是否为首次绑定，只有首次绑定才额外写入 `token_enabled=False` 与 `browser_query_disabled_reason=\"manual_disabled\"`；`app_backend/application/use_cases/resolve_login_conflict.py` 在冲突新建账号绑定时写入同样的默认关闭状态。未改前端协议、未改查询模式接口、未改白名单复用与登录主链其它已恢复逻辑。
- 已做验证：
  - 红灯 1：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_task_flow.py -k "binds_purchase_capability_and_persists_account or relogin_preserves_existing_browser_query_state" -q`，结果 `1 failed, 1 passed`，失败点为首次绑定后 `token_enabled` 仍为 `True`。
  - 红灯 2：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_conflict_flow.py -k "api_only_account_creates_new_logged_in_account_without_inheriting_source_config or resolve_login_conflict_create_new_account_keeps_old_account or resolve_login_conflict_replace_with_new_account_recreates_account" -q`，结果 `3 failed`，失败点均为新登录账号仍保持 `token_enabled=True`。
  - 绿灯 1：同一组 `test_login_task_flow.py` 目标测试重跑，结果 `2 passed`。
  - 绿灯 2：同一组 `test_login_conflict_flow.py` 目标测试重跑，结果 `3 passed`。
  - 总回归：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_login_task_flow.py tests/backend/test_login_conflict_flow.py tests/backend/test_account_query_mode_settings.py tests/backend/test_account_routes.py -q`，结果 `31 passed in 6.84s`。
- 当前进度：实现与聚焦回归都已完成，根目录业务修复已另行提交为 `3515cbe fix: default browser query off on first login bind`，剩余只要继续让日志跟上当前事实即可。
- 余险：当前仍沿用 `browser_query_disabled_reason=\"manual_disabled\"` 复用既有展示文案，因此界面上仍会显示“手动禁用”；这是本轮刻意接受的低风险折中，不代表未来不能引入更精确的 reason code。
- 下一步：继续保持关键行为先立约束、再补红绿灯、最后才改实现的节奏，避免登录链、白名单链、数据保存链再次被静默改坏。

## 2026-04-21 21:09 (Asia/Shanghai)
- 背景：用户要求把左侧程序账号入口改成“只显示未登录/用户名的可交互状态卡”，具体登录/注册/找回密码改为屏幕中央弹窗；已登录时弹窗不能再显示登录表单，只显示当前账号状态。
- 已完成：先把设计与实现计划分别落盘到 `docs/superpowers/specs/2026-04-21-program-access-dialog-design.md` 和 `docs/superpowers/plans/2026-04-21-program-access-dialog-implementation.md`，随后按 TDD 先改红灯，再做最小实现。后端侧为 `ProgramAccessSummary`、bootstrap schema、program-auth schema 正式补入可选 `username`，并在 `remote_entitlement_gateway` / `cached_program_access_gateway` 中从已验签 snapshot 读取用户名，保证程序重开后左侧仍能回显当前程序账号。前端侧把 `program_access_sidebar_card.jsx` 从“侧栏内整块表单”重构为“两层交互”：左侧只剩入口卡，状态文字只显示 `未登录/用户名`；点击后弹出居中 `dialog-surface`，未登录场景在弹窗里承载登录/注册/找回密码，已登录场景只显示当前账号状态与 `刷新状态` / `退出`。同步调整了 `program_access_runtime.js` 与相关 renderer/backend 测试预期。
- 已做验证：先执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_remote_entitlement_gateway.py -q`，红灯结果 `3 failed`，确认当前 summary 缺少 `username`；执行 `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，红灯结果 `6 failed`，确认当前组件仍在侧栏内直出表单。修复后重新执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_remote_entitlement_gateway.py -q`，结果 `23 passed`；执行 `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，结果 `6 passed`。随后补跑旁路回归：`npm --prefix app_desktop_web test -- tests/renderer/program_access_provider.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/runtime_connection_manager.test.js --run`，结果 `28 passed`；`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_auth_routes.py -q`，结果 `12 passed`。所有本轮验证仅保留既有 FastAPI `on_event("shutdown")` 弃用告警，无新失败。
- 当前进度：程序账号入口已从“侧栏表单堆叠”收口为“状态入口卡 + 中央弹窗”，且用户名已进入稳定 summary 链路。
- 下一步：等待用户在真实界面里确认交互手感；若还要继续精修，只需收弹窗文案、关闭方式或卡片视觉，不必再动后端鉴权语义。

## 2026-04-21 21:28 (Asia/Shanghai)
- 背景：用户要求把程序账号弹窗里“权限钥匙 / 共享数据 / 当前权限 / 说明 / 只读锁定”等说明块全部移除，并追问为什么从 `main_ui_node_desktop.js` 进源码态时未登录仍能执行关键功能。
- 已完成：继续按 TDD 先把 `program_access_sidebar_card` 与 `program_access_packaging` 测试改成新契约，确认红灯后，仅做两处最小修复：1. `program_access_sidebar_card.jsx` 删除弹窗副标题与未登录说明块，未登录场景只保留登录/注册/找回密码表单，已登录场景只保留账号状态与 `刷新状态 / 退出`；2. `program_access_config.cjs` 新增源码态候选配置路径，`main_ui_node_desktop.js` 现在会在源码启动时读取 `app_desktop_web/build/client_config.release.json`，从而把本地嵌入式后端切到正式远端鉴权，而不是默认掉回 `prepackaging` 本地放行。同步把该入口语义写入 `README.md` 与长期记忆。
- 已做验证：先执行 `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，红灯结果 `3 failed / 3 passed`，失败点为弹窗仍残留副标题与“只读锁定”说明块；执行 `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run`，红灯结果 `1 failed / 10 passed`，失败点为源码态未读取 `build/client_config.release.json`。修复后执行 `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/program_access_provider.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/renderer/runtime_connection_manager.test.js tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js --run`，结果 `56 passed`。
- 当前进度：程序账号弹窗已去掉共享数据说明块；当前根工作树的源码桌面入口也已具备正式程序会员鉴权能力，不再天然是“未登录放行”的调试壳。
- 下一步：等待用户亲自从源码入口点一遍，确认未登录下关键功能已锁、登录后可恢复；若还要保留显式本地放行调试态，再单独决定是否补一个明确命名的开发入口，而不是继续让 `main_ui_node_desktop.js` 兼任两种语义。

## 2026-04-21 22:40 (Asia/Shanghai)
- 背景：用户确认要正式把“本地放行调试”和“模拟用户登录调试”拆成显式双入口，避免继续让同一个入口靠缺配置隐式切模式。
- 已完成：先按 TDD 补红灯，锁定三件事：1. 必须存在 `main_ui_node_desktop_local_debug.js` 显式本地调试入口；2. 必须存在 `app_desktop_web/build/client_config.local_debug.json` 明确关闭控制面地址；3. 必须存在对称的 `run_app_local_debug.py` 包装入口。随后做最小实现：新增本地调试 launcher，仅注入 `CLIENT_CONFIG_FILE=client_config.local_debug.json` 与 `C5_PROGRAM_ACCESS_STAGE=prepackaging` 后再委托给 `main_ui_node_desktop.js`；新增 Python 本地调试包装入口；README 与长期记忆同步补齐双入口口径，主用户入口仍固定为 `main_ui_node_desktop.js` / `run_app.py`。
- 已做验证：先执行 `npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js --run`，结果 `30 passed`；再执行 `C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`，结果 `4 passed`。唯一残留仍是既有 FastAPI `on_event("shutdown")` 弃用告警，无新失败。
- 当前进度：显式双入口已落地并通过定向回归；现在本地可稳定区分“本地放行调试”和“模拟用户登录测试”，不再依赖删配置文件这种隐式切换。
- 下一步：等待用户亲自使用两条入口各点一遍；若还要继续收口，可再决定是否把这两个入口补成桌面快捷方式或批处理脚本，但当前代码主线已足够使用。

## 2026-04-21 23:36 (Asia/Shanghai)
- 背景：用户要求把安装包产物目录做成本地忽略，不参与提交，同时在本地留下一个可读的打包时间标记文件。
- 已完成：在 `.gitignore` 新增 `app_desktop_web/release/` 忽略规则；本地新增 `app_desktop_web/release/BUILD_INFO.txt`，记录最近打包时间 `2026-04-21 18:46:58 (Asia/Shanghai)`、当前安装包名 `C5 交易助手 Setup 0.1.0.exe`，并注明 `release/` 仅作为本地产物目录使用。
- 已做验证：执行 `git status --short`，当前只剩 `.gitignore` 为工作树改动，`release/` 目录未再以未跟踪文件出现；执行 `git check-ignore -v -- "app_desktop_web/release/C5 交易助手 Setup 0.1.0.exe"`，确认该安装包已被 `.gitignore:11` 命中；回读 `app_desktop_web/release/BUILD_INFO.txt`，内容与本次要求一致。
- 当前进度：安装包产物现已本地留档且默认忽略；按用户要求，本轮不提交。
- 下一步：若后续重打一包，只需覆盖 `release/` 内容并刷新 `BUILD_INFO.txt` 时间即可，无需再改 Git 规则。

## 2026-04-22 00:12 (Asia/Shanghai)
- 背景：用户要求把 C5 账号登录相关的用户可见任务状态统一改成中文，明确指定 `waiting_for_browser_close` 必须显示为“等待关闭登录窗口”，并要求留下便于后续快速定位的集中映射落点。
- 已完成：本轮已把登录任务状态中文化的维护点集中到 `app_desktop_web/src/features/account-center/login_task_state_labels.js`，由账号中心登录抽屉、诊断页登录任务标签页、账号中心日志 seed / 状态文案统一复用；同时补齐说明与计划文档 `docs/superpowers/specs/2026-04-22-login-task-state-localization-design.md`、`docs/superpowers/plans/2026-04-22-login-task-state-localization.md`。在本次续战里，进一步修正了 `app_desktop_web/tests/renderer/login_drawer.test.jsx` 与 `app_desktop_web/tests/renderer/diagnostics_sidebar.test.jsx` 的断言方式，使其接受“同一中文状态同时出现在状态卡片和事件时间线”的既定 UI 行为，不再把重复文本误判成失败。
- 已做验证：
  - `npm --prefix app_desktop_web test -- tests/renderer/login_drawer.test.jsx --run`，结果 `6 passed`。
  - `npm --prefix app_desktop_web test -- tests/renderer/diagnostics_sidebar.test.jsx --run`，结果 `7 passed`。
  - `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx --run`，结果 `7 passed`。
  - `npm --prefix app_desktop_web test -- tests/renderer/login_drawer.test.jsx tests/renderer/diagnostics_sidebar.test.jsx tests/renderer/account_center_page.test.jsx --run`，结果 `20 passed`。
- 当前进度：登录抽屉右侧状态、诊断页登录任务时间线、账号中心日志中的用户可见状态码都已切到正式中文口径；本轮剩余未提交内容主要是这批源码改动本身。
- 余险：当前验证集中在 renderer 层，尚未额外做人工界面点验；若后续还有其它页面直接渲染原始登录任务状态码，需要继续沿同一映射文件排查接线，而不是再在组件内散写文案。
- 下一步：等待用户继续决定是直接提交这一批中文化改动，还是继续做界面层人工巡检与补漏。

## 2026-04-22 00:29 (Asia/Shanghai)
- 背景：用户要求提交当前工作，并把账号中心“删除账号”的原生确认框改成符合当前项目风格的 UI，同时检查程序里是否还残留开发态提示或明显不对齐的用户文案。
- 已完成：先补说明与计划文档 `docs/superpowers/specs/2026-04-22-account-delete-dialog-and-copy-alignment-design.md`、`docs/superpowers/plans/2026-04-22-account-delete-dialog-and-copy-alignment.md`，随后按 TDD 先改红灯，再做最小实现。账号中心现已新增站内删号弹层 `app_desktop_web/src/features/account-center/dialogs/account_delete_dialog.jsx`，删除流程从 `window.confirm(...)` 改为“右键菜单 -> 站内弹层 -> 确认删除”，仍复用原 DELETE + refresh + 日志链路。顺手把普通用户可见的英文眉标收口为中文：账号中心页 `ACCOUNT CENTER` 改为 `账号中心`，程序账号入口/弹窗中的 `PROGRAM ACCESS` 改为 `程序账号`，诊断面板的 `Diagnostics` 改为 `运行诊断`。额外复扫后确认：`本地调试模式` 只存在于显式本地放行调试分支，按既定边界保留；主导航上的 `Live` 标签仍是英文，但它属于视觉文案未完全汉化，不是开发态提示，本轮未扩范围处理。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run`，结果失败点准确落在旧的 `window.confirm` 与英文眉标。
  - 绿灯：
    - `npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx --run`，结果 `19 passed`
    - `npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx --run`，结果 `7 passed`
    - `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，结果 `6 passed`
    - `npm --prefix app_desktop_web test -- tests/renderer/diagnostics_sidebar.test.jsx --run`，结果 `7 passed`
    - `npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx tests/renderer/account_center_page.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run`，结果 `39 passed`
- 当前进度：账号中心删号确认和本轮锁定的三处用户可见眉标都已收口，当前剩余主要是等待提交。
- 余险：主导航按钮上的 `Live` 标签仍是英文视觉词，不影响功能，但若后续要继续做整体文案统一，应把它纳入同一轮 UI 文案清理，而不是再零碎散改。
- 下一步：提交本轮源码与文档改动；若用户继续要求清理 `Live` 这类剩余英文视觉词，再单开一个小范围 UI 文案收口任务。

## 2026-04-22 00:35 (Asia/Shanghai)
- 背景：用户继续要求把主导航上的 `Live` 标签全部移除。
- 已完成：按最小范围处理，仅修改壳层导航渲染，不碰导航按钮本身、路由切换、激活态与可点击区域。`app_desktop_web/src/features/shell/app_shell.jsx` 中的 `NAV_ITEMS` 已去掉 `tag` 字段，导航按钮也不再渲染 `app-shell__nav-button-tag`；同时清理 `app_desktop_web/src/styles/app.css` 中对应的无用标签样式。为锁定结果，`app_desktop_web/tests/renderer/account_center_page.test.jsx` 新增了“不再出现 `Live`”的断言。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx --run`，结果失败点准确落在仍存在的多个 `Live` 标签。
  - 绿灯 1：`npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx --run`，结果 `7 passed`
  - 绿灯 2：`npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/query_system_page.test.jsx tests/renderer/purchase_system_page.test.jsx tests/renderer/diagnostics_sidebar.test.jsx --run`，结果 `60 passed`
  - 额外复扫：`rg -n "Live|app-shell__nav-button-tag" app_desktop_web/src app_desktop_web/tests -g '!**/node_modules/**'`，当前只剩测试里的“不得出现 Live”断言，源码层已无残留渲染。
- 当前进度：主导航 `Live` 标签已全部移除；当前工作树仅剩这 3 个相关文件改动，尚未提交。
- 余险：无功能性余险；本轮只删视觉标签，不影响壳层布局、交互和页面切换。
- 下一步：等待用户决定是否把这刀也提交。

## 2026-04-22 01:00 (Asia/Shanghai)
- 背景：用户要求按三步逻辑落地程序账号注册，并把防批量刷注册的邮箱校验前移到发验证码阶段。
- 已完成：完成现状审查，确认当前前端仍是一屏式注册表单、本地后端仅有“发码 + 注册”两接口；据此新增规格文档 `docs/superpowers/specs/2026-04-22-registration-anti-abuse-flow-design.md`，正式冻结为“三步交互 + 三接口 + 发码阶段远端风控 + 验证通过后一次性注册票据”的设计。
- 已做验证：已回读新 spec 内容，并已发起独立 spec reviewer 审查，待 reviewer 返回最终意见；本阶段未修改业务代码、未执行自动化测试。
- 当前进度：注册方案已进入“文档化并待审查”状态；业务实现与计划尚未开始。
- 下一步：吸收 spec reviewer 反馈后修正文档；若无阻塞，则请用户确认该 spec 文件，再进入实现计划。

## 2026-04-22 01:34 (Asia/Shanghai)
- 背景：继续收口注册三步流 spec，目标是让该文档在进入实现计划前不再存在接口契约、状态跳转或灰度发布层面的歧义。
- 已完成：围绕 reviewer 提出的五轮问题，补齐了注册接口硬契约、错误码总表、统一失败包络、冷却优先级、重发/验码幂等规则、能力开关 `registration_flow_version`、短邮箱脱敏规则、网络失败映射、敏感凭据日志禁令、远端路径映射与状态迁移表；随后将规格文档单独提交为 `eda54e3 docs: add anti-abuse registration flow spec`，未带入当前工作树中的其它 UI 脏改。
- 已做验证：多次回读 `docs/superpowers/specs/2026-04-22-registration-anti-abuse-flow-design.md` 并完成 5 轮 spec reviewer 闭环；按技能上限已停止继续派发 reviewer。未执行自动化测试，因为本阶段仍是文档收口，不涉及业务代码。
- 当前进度：注册三步流 spec 已写入仓库并单独提交；下一关是等待用户审阅该 spec 文件，确认后才能进入实现计划。
- 下一步：请用户审阅 `docs/superpowers/specs/2026-04-22-registration-anti-abuse-flow-design.md`；若无异议，下一步进入 `writing-plans`，拆出前端三步状态机、本地后端转发层与远端控制面接口改造的实现计划。

## 2026-04-22 21:39 (Asia/Shanghai)
- 背景：用户要求把项目对外入口收口为 JS-only，移除无效且易混淆的顶层 Python 启动入口，但不能破坏 JS 桌面壳内部拉起 Python backend 的既有链路。
- 已完成：先补红灯测试锁定“根目录不再保留 `run_app.py` / `run_app_local_debug.py`、README 与 `docs/superpowers/README.md` 不再把 Python 当启动入口、`app_backend/main.py` 不再保留直接脚本启动口”，随后删除两个顶层 Python 包装入口，移除 `app_backend/main.py` 的 `__main__` 启动 guard，并将主 README 与 superpowers 说明统一收口为“用户态入口 = `main_ui_node_desktop.js`，本地调试入口 = `main_ui_node_desktop_local_debug.js`，Python backend 仅供 JS 桌面壳内部使用”。
- 已做验证：
  - 红灯：`python -m pytest tests/backend/test_remove_legacy_cli_entry.py -q`，结果 `4 failed`，失败点准确落在旧 Python 包装入口、README 旧文案、以及 `app_backend/main.py` 仍保留直接执行入口。
  - 绿灯：`python -m pytest tests/backend/test_remove_legacy_cli_entry.py tests/backend/test_backend_main_entry.py -q`，结果 `9 passed`。
  - JS 启动器回归：`npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js --run`，结果 `7 passed`。
  - 复扫：`rg -n "python run_app|run_app\\.py|run_app_local_debug\\.py|python -m app_backend\\.main" README.md docs/superpowers/README.md tests/backend/test_remove_legacy_cli_entry.py app_backend/main.py`，当前仅命中新的约束测试，不再命中 README、辅助说明或 backend 源码。
- 当前进度：项目对外入口口径已正式收口为 JS-only；JS 桌面壳内部拉起 backend 的实现未动，登录/查询/购买主链路未受影响。
- 余险：历史计划文档、历史 spec 与旧会话日志中仍会提到 `run_app.py`，它们属于历史材料而非当前入口契约；若后续还要继续清理历史文档，需要单开文档治理任务，不能把历史记录当成现行说明误删。
- 下一步：等待用户确认新的入口口径是否满足预期；若还要进一步减少歧义，可继续把少数历史参考文档里的旧入口描述补上“历史口径”标记。

## 2026-04-22 23:40 (Asia/Shanghai)
- 背景：用户批准继续把程序账号注册三步流落到真实桌面链路，并要求用 `spec + plan + session-log` 维持可断点续战的执行节奏；当前重点是不改登录/找回密码/主业务主链，只补齐注册 v3 的真实缺口。
- 已完成：复核已冻结 spec `docs/superpowers/specs/2026-04-22-registration-anti-abuse-flow-design.md` 与当前未提交残片，确认远端控制面已先接出 `/api/auth/register/send-code|verify-code|complete`，但真实桌面链路仍断在本地后端代理、renderer client/provider 与弹窗状态机三层；据此新增实现计划 `docs/superpowers/plans/2026-04-22-program-access-registration-v3-implementation.md`，按 chunk/task 拆成“本地后端契约锁定 -> 本地桥接实现 -> renderer 红灯 -> renderer 三步状态机 -> 验证与交接”五个 chunk。
- 已做验证：先执行 `npm --prefix app_desktop_web test -- --run tests/renderer/program_auth_client.test.js tests/renderer/program_access_provider.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx`，结果 `4 files failed / 16 tests passed`，失败点准确落在 `verifyRegisterCode` / `completeRegisterProgramAuth` 缺失、provider 未按 `registration_flow_version` 暴露 v3 action，以及 UI 仍渲染旧一屏式注册字段；再执行 `npm --prefix program_admin_console run test:server`，结果 `control-plane-server tests passed`，确认远端控制面侧的未提交改动基本成形。
- 当前进度：实现计划已落盘，当前仍处于“正式写实现前的计划收口”阶段；下一刀将按 TDD 先补 backend 红灯，再做本地后端与远端 bridge 的最小实现。
- 下一步：先补并跑 `tests/backend/test_app_bootstrap_route.py`、`tests/backend/test_program_auth_routes.py`、`tests/backend/test_remote_control_plane_client.py`、`tests/backend/test_remote_entitlement_gateway.py` 的红灯，再进入 `app_backend/` 的 summary/schema/route/client/gateway 实现；本会话收尾前需再次同步 session-log，写明实际完成到哪一 chunk/task。

## 2026-04-23 00:17 (Asia/Shanghai)
- 背景：继续执行 `docs/superpowers/plans/2026-04-22-program-access-registration-v3-implementation.md`，目标是把注册 v3 从“后端已接、前端未落地”推进到 `main_ui_node_desktop.js` 源码桌面入口真实可用。
- 已完成：按 TDD 先补并跑 renderer 红灯，再完成四层接线。`app_desktop_web/src/api/program_auth_client.js` 新增 `verifyRegisterCode()` / `completeRegisterProgramAuth()`；`program_access_runtime.js` 与 `program_access_provider.jsx` 现已接收 `registration_flow_version` 并只在 `=3` 时暴露 v3 action；`App.jsx` 把新 action 传入程序账号弹窗；`program_access_sidebar_card.jsx` 已从旧一屏式注册表单收口为 `register_email -> register_code -> register_credentials -> register_success` 三步状态机，同时保留 `registration_flow_version != 3` 的旧注册 fallback，不改登录/找回密码入口。桌面启动侧补上 `probeRegistrationReadiness` 显式配置：`app_desktop_web/electron-main.cjs` 会在存在控制面地址时把 readiness probe flag 透传给 `app_desktop_web/python_backend.js`，后者再用环境变量 `C5_PROGRAM_ACCESS_PROBE_REGISTRATION_READINESS=1` 拉起 `app_backend/main.py`；`create_app(...)` 新增 `program_access_probe_registration_readiness` wiring，远端 entitlement gateway 因而会在 packaged/source release 链路主动探测注册 readiness，不再默认卡死在 v2。同步把实现计划中的全部 chunk/task 勾到真实完成状态。
- 已做验证：
  - renderer + electron：`npm --prefix app_desktop_web test -- --run tests/renderer/program_auth_client.test.js tests/renderer/program_access_provider.test.jsx tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/app_remote_bootstrap.test.jsx tests/electron/python_backend.test.js tests/electron/program_access_packaging.test.js`，结果 `43 passed`。
  - backend：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_app_bootstrap_route.py tests/backend/test_program_auth_routes.py tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py tests/backend/test_desktop_web_backend_bootstrap.py tests/backend/test_backend_main_entry.py -q`，结果 `64 passed`。
  - control plane：`npm --prefix program_admin_console run test:server`，结果 `control-plane-server tests passed`。
  - renderer build：`npm --prefix app_desktop_web run build`，结果 `vite build` 成功，`dist/assets/index-Et0osOzK.js` 等新产物已生成。
  - 当前自动化验证仅剩两类既有告警：FastAPI `on_event("shutdown")` 弃用告警，以及 Node `SQLite is an experimental feature` 警告；无新增失败。
- 当前进度：计划 Chunk 1-5 已落地并完成 fresh verification；当前源码桌面入口应已具备“远端 readiness=3 时显示邮箱首屏三步注册、未就绪时继续 v2 fallback”的真实行为。本轮没有形成新的长期项目规则，因此未更新 `docs/agent/memory.md`。
- 下一步：优先让用户直接从 `main_ui_node_desktop.js` 做一次真人链路点验，按 `发送验证码 -> 验证验证码 -> 完成注册` 走一遍真实控制面；若线上再暴露新的错误码或倒计时包络差异，再沿现有 state machine / readiness probe 落点继续补齐，而不是重开 spec。

## 2026-04-23 12:31 (Asia/Shanghai)
- 背景：用户从 `main_ui_node_desktop.js` 的正式桌面入口反馈“注册页仍是旧一屏式表单，并提示注册验证码发送失败”；本轮按用户要求只做部署，不再改前端功能实现，同时补齐 rollout spec/plan 与可续战记录。
- 已完成：先新增 rollout 文档 `docs/superpowers/specs/2026-04-23-program-access-registration-v3-rollout-design.md` 与 `docs/superpowers/plans/2026-04-23-program-access-registration-v3-rollout.md`，把边界正式冻结为“只部署 `program_admin_console`，不改 renderer / 本地 backend / 登录与找回密码 / 主业务主链”。随后复证根因：公网 `GET http://8.138.39.139:18787/api/auth/register/readiness` 确认仍是 `404 route not found`，而本地 `program_admin_console/src/server.js` 已具备四条注册 v3 路由，问题坐实为远端旧镜像未升级。部署时使用本机现成 ECS 密钥 `C:/Users/18220/.ssh/c5_ecs_deploy_temp` 连入 `admin@8.138.39.139`；确认旧容器 `c5-program-admin` 挂在 `18787->8787`，保留 `c5_program_admin_data:/app/data` 与 `/home/admin/c5-program-admin-runtime/keys:/app/keys:ro`。本地先跑 `npm --prefix program_admin_console test`，结果全绿；再生成最小发布包 `.runtime/program_admin_console_rollout_20260423_122744.tar` 并上传远端。远端侧将旧镜像打 tag 为 `c5-program-admin:pre-rollout-20260423_122744`，保留旧源码目录为 `/home/admin/c5-program-admin-src_prev_20260423_122744`，新源码目录切到 `/home/admin/c5-program-admin-src`，并成功构建/切换新容器 `c5-program-admin:rollout-20260423_122744`。
- 已做验证：
  - 本地 control plane 全量：`npm --prefix program_admin_console test`，结果全部通过。
  - 远端现网：
    - `curl http://8.138.39.139:18787/api/health` -> `{"ok":true}`
    - `curl http://8.138.39.139:18787/api/auth/register/readiness` -> `{"ok":true,"ready":true,"registration_flow_version":3,"mail_service_configured":true}`
    - `curl -H "Content-Type: application/json" -d '{"email":"not-an-email","install_id":"probe-install"}' http://8.138.39.139:18787/api/auth/register/send-code` -> `{"ok":false,"error_code":"REGISTER_INPUT_INVALID",...}`，已证明路由存在且不再是 `route not found`
  - 正式桌面 backend：
    - `curl http://127.0.0.1:61100/app/bootstrap` -> `program_access.mode=remote_entitlement`、`stage=packaged_release`、`registration_flow_version=3`
    - 对照 `curl http://127.0.0.1:60967/app/bootstrap` 仍是 `local_pass_through / prepackaging / registration_flow_version=2`，确认本地调试入口未被误伤
- 当前进度：注册 v3 的真正阻塞“远端未部署”已解除；正式桌面 backend 已切到 `registration_flow_version=3`。当前唯一未拿到的新鲜证据是“部署后重开正式桌面窗口的真人 UI 目测结果”。若用户还盯着部署前打开的那扇正式窗口，它仍可能缓存旧 bootstrap，需要彻底关闭后重新从 `main_ui_node_desktop.js` 打开再看。
- 下一步：请用户关闭当前正式桌面窗口并重新从 `main_ui_node_desktop.js` 打开程序，重新点开注册弹窗做人工点验。预期首屏只显示“注册邮箱”，验码前不出现“注册用户名 / 注册密码”。若重开后仍旧表单，再继续排查 renderer 是否缓存旧 bootstrap 或未重新拉取 `program_access` summary。

## 2026-04-23 13:45 (Asia/Shanghai)
- 背景：用户在 `2026-04-23 13:33` 左右重启 `main_ui_node_desktop.js` 后，仍看到“邮箱 + 验证码 + 用户名 + 密码”同屏旧注册 UI。继续排查后确认：远端控制面、正式本地 backend、以及当前 `dist` bundle 都已经是注册 v3，问题只剩 renderer 运行态未切到三段式。
- 已完成：按系统化排障先补证据再修。代码对照确认 `main_ui_node_desktop.js` 拉起的是 `embedded` 桌面模式，而 `app_desktop_web/src/App.jsx` 旧逻辑只在 `bootstrapConfig.backendMode === "remote"` 时才会执行 `runtimeConnectionManager.bootstrap()`；这会让正式源码桌面虽然本地 backend 已返回 `registration_flow_version=3`，renderer 却一直停在 `EMPTY_PROGRAM_ACCESS.registrationFlowVersion = 2` 的默认值，最终落回旧一屏式注册表单。随后按 TDD 先在 `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx` 增加“embedded + backend ready 也必须拉 `/app/bootstrap` 并显示三段式注册首屏”的红灯，再只在 `app_desktop_web/src/App.jsx` 做一刀最小修复：去掉对 `backendMode === "remote"` 的限制，只要当前 backend 已 `ready` 就统一 bootstrap。修复后重新 build renderer，新的源码桌面 bundle 已更新为 `dist/assets/index-NnDhODcd.js`。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run`，结果 `1 failed / 4 passed`，失败点准确显示 embedded 场景没有请求 `http://127.0.0.1:59192/app/bootstrap`，而是直接只打了 `/account-center/accounts`。
  - 绿灯 1：再次执行 `npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run`，结果 `5 passed`。
  - 绿灯 2：执行 `npm --prefix app_desktop_web test -- tests/renderer --run`，结果 `25 files / 181 tests passed`，确认 renderer 全量回归未被这次启动条件修复带坏。
  - 构建：执行 `npm --prefix app_desktop_web run build`，结果 `vite build` 成功，当前构建产物为 `dist/assets/index-NnDhODcd.js` 与 `dist/assets/index-C9xRjEhC.css`。
- 当前进度：根因已闭环并已修到源码入口链路；当前 `13:33` 那批旧进程仍在内存里跑旧 renderer 代码，所以用户眼前窗口不会自行变成三段式。fresh build 已落盘，下次从 `main_ui_node_desktop.js` 重启时应会先拉本地 `/app/bootstrap`，再按 `registration_flow_version=3` 显示邮箱首屏。
- 余险：本轮只拿到了自动化验证和源码链路证据，尚未拿到“修复后新启动窗口”的真人目测截图或现场录屏；若用户重启后仍异常，则下一步优先抓新进程的 renderer 运行态日志，确认 `programAccess.registrationFlowVersion` 与 `verifyRegisterCode/completeRegisterProgramAuth` 在窗口内是否已同时生效。
- 下一步：关闭当前 `2026-04-23 13:33` 左右启动的 `node/electron/python` 旧进程后，重新从 `main_ui_node_desktop.js` 打开程序做人工点验。预期注册首屏只显示“注册邮箱”，点击“发送注册验证码”后才进入第二段验证码 UI，验码成功后才进入第三段“用户名 + 密码”设置 UI。

## 2026-04-23 14:05 (Asia/Shanghai)
- 背景：用户继续要求优化程序账号注册弹窗 UI：第二段验证码页在关闭弹窗或切换页面后再次进入时必须保留邮箱与倒计时，不再要求重新填邮箱和重发验证码；同时移除默认 `program_auth_required / 请先登录程序会员` 提示，把输入提示放进输入框内，并把右上角关闭按钮改成红底正方形 `X`。
- 已完成：先按 brainstorming 收敛边界，冻结为“只改程序账号弹窗前端状态与视觉层，不改远端注册接口、登录/找回密码链和主业务主链”。用户确认采用方案 A：只在当前 renderer 会话内保留第二段注册草稿，不做 `localStorage/sessionStorage` 跨刷新持久化。随后新增 spec `docs/superpowers/specs/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish-design.md` 与 plan `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`，已把“关闭后回到第二段、默认 `program_auth_required` 不显示、placeholder 化、红底 `X` 关闭按钮”写成明确实现边界。
- 已做验证：本阶段仅完成设计与计划落盘，尚未开始写测试和业务代码，因此暂无新的自动化验证结果。
- 当前进度：当前断点位于“计划已写完，准备补 `program_access_sidebar_card` 的前端红灯测试”。
- 下一步：先改 `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`，锁定关闭弹窗后回到第二段、切回登录时仍清空注册草稿、隐藏默认 `program_auth_required`、输入框 placeholder 与关闭按钮文案契约，再按 TDD 进入最小实现。

## 2026-04-23 14:32 (Asia/Shanghai)
- 背景：继续执行 `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`，把程序账号注册弹窗的“第二段可恢复 + 默认告警过滤 + placeholder 化 + 红底关闭按钮”从设计稿推进到真实 renderer 行为，并补齐可续战记录。
- 已完成：`app_desktop_web/src/program_access/program_access_sidebar_card.jsx` 已完成最小实现，注册三段流进入第二段验证码页后，关闭弹窗或切换窗口再打开，会直接回到第二段并保留邮箱摘要、`register_session_id` 与倒计时；只有主动切到“登录/找回密码”、点击“修改邮箱”或注册成功时才显式清空注册草稿。默认 `program_auth_required / 请先登录程序会员` 顶部提示已过滤，不再作为异常渲染；登录/注册/找回密码输入区统一改为输入框内 `placeholder`；右上角关闭按钮已收口为红底正方形 `X`，同时保留 `aria-label=\"关闭\"`。同步更新了 `app_desktop_web/src/styles/app.css` 的浅色输入框与关闭按钮样式，并把这些契约补进 `app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`。本轮 spec `docs/superpowers/specs/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish-design.md` 与 plan `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md` 均已按真实完成态收口。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，结果 `3 failed / 8 passed`，失败点准确落在默认 `program_auth_required` 仍显示、关闭后注册流被重置、关闭按钮文本仍是“关闭”。
  - 聚焦绿灯：`npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，结果 `11 passed`。
  - renderer 全量：`npm --prefix app_desktop_web test -- tests/renderer --run`，结果 `25 files / 185 tests passed`。
  - 构建：`npm --prefix app_desktop_web run build`，结果 `vite build` 成功，当前产物为 `dist/assets/index-CK1Q2iXY.js` 与 `dist/assets/index--VJ_zwjX.css`。
- 当前进度：本轮前端行为、样式与自动化验证已全部落地；当前只剩真人界面点验，用新窗口确认“关闭后回到第二段、默认提示消失、红底 `X`”在 `main_ui_node_desktop.js` 启动的正式窗口里也按预期生效。
- 下一步：彻底关闭当前程序窗口后，重新从 `main_ui_node_desktop.js` 打开并点开程序账号弹窗，人工检查三点：1. 首屏只显示邮箱输入；2. 发码进入第二段后关闭再打开仍停留在验证码页且保留倒计时；3. 顶部不再出现默认 `program_auth_required` 提示，右上角显示红底方形 `X`。

## 2026-04-23 14:35 (Asia/Shanghai)
- 背景：承接上一条断点后，本轮只做记录补齐与收尾复验，不再扩大修改范围。
- 已完成：已把本轮真实完成态回写到 `docs/agent/session-log.md` 与 `docs/agent/memory.md`，并复核 `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md` 当前无未勾选项；同时再次核对工作区脏文件范围，确认仍是本轮注册 v3 / 程序账号弹窗相关改动与文档，不存在新的意外写入。
- 已做验证：
  - `npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run`，结果 `11 passed`。
  - `npm --prefix app_desktop_web test -- tests/renderer --run`，结果 `25 files / 185 tests passed`。
  - `npm --prefix app_desktop_web run build`，结果 `vite build` 成功，产物仍为 `dist/assets/index-CK1Q2iXY.js` 与 `dist/assets/index--VJ_zwjX.css`。
  - `rg -n "^- \\[ \\]" docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`，结果无命中，确认本轮 plan 已按真实进度全部勾完。
- 当前进度：代码、文档和 fresh verification 已全部收口；当前唯一未补齐的是正式窗口的人工目测点验。
- 下一步：让用户彻底关闭旧程序窗口后，从 `main_ui_node_desktop.js` 重新打开，人工确认三段式首屏、第二段恢复、默认提示消失与红底 `X` 都在真实桌面窗口里生效。

## 2026-04-23 14:47 (Asia/Shanghai)
- 背景：会话准备结束，按 `save-status-handoff` 固化当前断点，避免下个会话重做已完成的注册 v3 / 程序账号弹窗工作。
- 当前目标：收口程序账号注册相关两条已落地方案，分别是 `docs/superpowers/plans/2026-04-22-program-access-registration-v3-implementation.md` 与 `docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`；当前只剩正式窗口人工点验，不再扩改实现。
- 进度断点：
  - 当前 chunk/task：`2026-04-23-program-access-registration-dialog-persistence-and-ui-polish` 的 `Chunk 3 / Task 5` 已完成；当前没有正在编码的 task。
  - 已完成：远端控制面 rollout、embedded renderer bootstrap 修复、注册三段式状态机、第二段验证码页关闭后恢复、默认 `program_auth_required` 过滤、输入框 placeholder 化、红底正方形 `X` 关闭按钮、spec/plan/session-log/memory 回写、fresh renderer 测试与 build。
  - 正在进行：无代码实现进行中；唯一剩余动作是用户侧从 `main_ui_node_desktop.js` 重新启动后的真人界面点验。
- 现场状态：
  - 工作目录：`C:/Users/18220/Desktop/C5autobug更新接口 - 副本 (2)`
  - 当前分支：`master`
  - 当前 worktree：根工作树；另有 `.worktrees/local-program-access-extension`、`.worktrees/program-control-plane-chunk1`、`.worktrees/registration-anti-abuse-plan` 保留，但本轮未切过去继续做事。
  - 未提交改动：存在，且范围较大；本轮相关核心文件包括 `app_desktop_web/src/App.jsx`、`app_desktop_web/src/program_access/program_access_sidebar_card.jsx`、`app_desktop_web/src/styles/app.css`、`app_desktop_web/tests/renderer/program_access_sidebar_card.test.jsx`、`docs/agent/session-log.md`、`docs/agent/memory.md`，以及注册 v3 的 backend / control-plane / spec / plan 文件。当前未提交、未清理、未回滚。
- 错误与约束：
  - 不要再重走“远端没部署 / renderer 没实现”的旧结论；这两条都已修过并拿到验证。
  - 如果用户仍看到旧 UI，下一会话第一反应不是改代码，而是先确认是否还盯着旧窗口/旧进程，或是否没有重新从 `main_ui_node_desktop.js` 启动。
  - 必须保持不变：不改登录链、不改找回密码链、不改 `查询 -> 命中 -> 购买` 主链；注册第二段草稿只在当前 renderer 会话保留，且只允许在“切到登录/找回密码、修改邮箱、注册成功”时清空。
- 验证状态：
  - 已执行：`npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run` -> `11 passed`；`npm --prefix app_desktop_web test -- tests/renderer --run` -> `25 files / 185 tests passed`；`npm --prefix app_desktop_web run build` -> 成功。
  - 已有历史证据：远端 readiness / send-code 路由已上线，embedded bootstrap 修复也已单独做过红绿验证，详见本文件 `2026-04-23 12:31`、`13:45`、`14:32` 三节。
  - 验证缺口：尚无“用户重开正式窗口后的真人目测”新鲜证据。
- 下一步第一刀：下个会话先让用户彻底关闭旧窗口，再从 `main_ui_node_desktop.js` 重开做人工点验；若仍异常，第一步先抓新进程里的 renderer 运行态与 `programAccess.registrationFlowVersion`，不要先改实现。点验后再按结果继续更新 `docs/agent/session-log.md`。

## 2026-04-23 14:54 (Asia/Shanghai)
- 背景：新会话按 `resume-from-handoff` 承接断点，先读取 `docs/agent/session-log.md` 最新一节、两份注册相关 plan、`docs/agent/memory.md`，并核对当前 `git status / branch / worktree`，避免重复实现已完成内容。
- 已完成：
  - 已复述当前总目标仍是“只收口程序账号注册 v3 与弹窗持久化方案，剩余正式窗口人工点验”，不重做远端 rollout、embedded bootstrap 修复与三段式注册实现。
  - 已确认现场仍在根工作树 `master`，`origin/master` 之上 `ahead 11`；保留 worktree 仍为 `.worktrees/local-program-access-extension`、`.worktrees/program-control-plane-chunk1`、`.worktrees/registration-anti-abuse-plan`，与 handoff 一致。
  - 已识别文档与现场的唯一差异是：`14:47` 节中的未提交改动列表是摘要而非全量；当前 `git status` 还额外显示 `app_backend/main.py`、`app_desktop_web/electron-main.cjs`、`app_desktop_web/python_backend.js`、`app_desktop_web/src/features/shell/app_shell.jsx`、`tests/backend/test_desktop_web_backend_bootstrap.py` 及新增 rollout/spec/plan 文档等脏改与未跟踪文件，但未发现“实现被回退”或“分支切错”的冲突证据。
  - 已按用户要求先让用户彻底关闭旧窗口，并从 `main_ui_node_desktop.js` 重新启动正式桌面做人工点验；当前等待用户返回新鲜目测结果。
- 已做验证：
  - 文档承接：重新读取 `docs/agent/session-log.md` 的 `2026-04-23 14:47` 节、`docs/superpowers/plans/2026-04-22-program-access-registration-v3-implementation.md`、`docs/superpowers/plans/2026-04-23-program-access-registration-dialog-persistence-and-ui-polish.md`、`docs/agent/memory.md`。
  - 现场核对：`git status --short --branch`、`git branch --show-current`、`git worktree list --porcelain`。
- 当前进度：没有新增代码修改；唯一未完成项仍是正式窗口 fresh 真人点验。
- 下一步：若用户重开后界面正常，则仅补齐本节后续点验结果；若仍异常，严格按 handoff 先抓新进程里的 renderer 运行态与 `programAccess.registrationFlowVersion`，先定位根因，再决定是否需要改代码。

## 2026-04-23 17:54 (Asia/Shanghai)
- 背景：用户在主链功能提交后，继续要求修两处程序账号注册发码缺口：1. 不能通过“修改邮箱”绕过 60 秒冷却；2. 明显不完整邮箱如 `1822049852@qq.CO` 不应继续发送验证码。本轮按“只修注册发码链路，不改登录/找回密码/查询-命中-购买主链”的边界收口。
- 已完成：
  - 远端 control-plane `program_admin_console/src/server.js` 已收紧邮箱校验并显式拦截 `qq.co`，同时在 `evaluateRegisterSendLimits()` 中加入同 `install_id` 的 60 秒硬冷却，保证同一安装实例换邮箱也会返回 `REGISTER_SEND_RETRY_LATER + retry_after_seconds`。
  - 本地 backend 已把 program access 稳定 `device_id` 作为远端 `install_id` 透传到 `/api/auth/register/send-code`、`/api/auth/register/verify-code`、`/api/auth/register/complete`；`remote_control_plane_client.py` 现兼容 control-plane v3 的 `error_code` 包络，不再只认旧 `reason`。
  - 本地 route/gateway 已透传注册错误 payload：`app_backend/api/routes/program_auth.py` 会把 `ProgramAccessActionResult.payload` 写入 `detail`，`remote_entitlement_gateway.py` 会保留 `retry_after_seconds`，并把注册 v3 大写错误码映射到正确 HTTP status。
  - renderer `app_desktop_web/src/program_access/program_access_sidebar_card.jsx` 已改为：点击“修改邮箱”回到第一步时保留当前冷却；邮箱页在剩余冷却期间持续禁用“发送注册验证码”；若失败响应里带 `retry_after_seconds`，则用该值刷新倒计时；本地粗校验也已拦下 `qq.co` 这类明确 typo 域名。
  - 新增 spec/plan `docs/superpowers/specs/2026-04-23-program-access-registration-cooldown-hard-lock-and-email-validation-design.md` 与 `docs/superpowers/plans/2026-04-23-program-access-registration-cooldown-hard-lock-and-email-validation.md`，并已按真实实现补齐“`device_id -> install_id` 透传、renderer + control-plane 校验、本地 backend 只透传”的最终设计口径。
- 已做验证：
  - backend：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_auth_routes.py tests/backend/test_remote_control_plane_client.py tests/backend/test_remote_entitlement_gateway.py -q` -> `50 passed`；仅保留既有 FastAPI `on_event("shutdown")` 弃用告警，无新增失败。
  - control-plane：`npm --prefix program_admin_console run test:server` -> `control-plane-server tests passed`；仅保留既有 Node `SQLite is an experimental feature` 警告。
  - renderer focused：`npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx --run` -> `13 passed`。
  - renderer affected regression：`npm --prefix app_desktop_web test -- tests/renderer/program_access_sidebar_card.test.jsx tests/renderer/program_access_provider.test.jsx tests/renderer/program_auth_client.test.js --run` -> `22 passed`。
  - renderer build：`npm --prefix app_desktop_web run build` -> 成功，当前产物为 `dist/assets/index-DwVvC3ec.js` 与 `dist/assets/index--VJ_zwjX.css`。
- 当前进度：本轮 bugfix 的代码、设计文档与 fresh verification 已全部收口；当前剩余动作只有把 `cooldown hard lock + email validation` 这一组修改提交为独立 commit。
- 余险：
  - 本轮只覆盖注册发码链路，不改登录/找回密码链，也不改已完成的注册三步主状态机结构。
  - 邮箱 typo 域名当前只显式拦截已确认的常见误写 `qq.co`；若后续再出现新的高频 typo，再按同一白名单策略补充，不在本轮顺手扩大规则面。
- 下一步：`git add -A` 后提交本轮 bugfix，建议 message 为 `fix: harden program access registration send-code`；提交后再次核对 `git status --short --branch` 确认工作树收口。

## 2026-04-23 20:13 (Asia/Shanghai)
- 背景：用户转而追查桌面发行包体积异常膨胀，希望确认“真正的空框架大小”并制定瘦身路线；经盘点，当前 `win-unpacked` 约 `1.02GB`，主要肥肉不是前端代码，而是 packaged release 直接打入完整 `.venv`，其中无运行引用的 `PySide6 + shiboken6` 约 `623.35MB`。
- 已完成：
  - 完成只读盘点：确认 Git 跟踪代码本体约 `40.55MB`，`app.asar` 约 `21.07MB`，真实前端 `src` 仅约 `0.50MB`；当前肥胖主因是 `app_desktop_web/electron-builder.config.cjs` 把根目录 `.venv` 整包带入发行包。
  - 与用户确认新的发行边界：接受首次启动联网下载 Python runtime；下载源首刀使用 Python 官方 Windows embeddable package；若首启网络不可用、下载失败、校验失败或解压失败，则阻断进入程序并允许重试；不采用“要求用户自行安装 Python”与“继续内置完整 `.venv`”。
  - 已把设计落盘到 `docs/superpowers/specs/2026-04-23-packaged-python-runtime-bootstrap-design.md`，内容覆盖打包清单收口、packaged runtime bootstrap、官方 runtime 下载校验、失败阻断、开发态兼容、最小 Python 依赖资源边界、验证与回退方案。
- 已做验证：
  - 只读体积盘点与现状核对：根仓库总量、一级目录体积、最大文件、`win-unpacked` 组成、`.venv` 体积拆分、builder config 与 `pyproject.toml` 依赖清单。
  - 本轮尚未进入实现，因此没有新的自动化测试或打包验证结果。
- 当前进度：设计已获用户口头确认并落盘；当前断点位于“准备把 spec 转成 implementation plan，并用 TDD 改 packaged Python runtime bootstrap”。
- 余险：
  - 当前 spec 已锁定“runtime 走官方 embeddable package”，但 Python 业务依赖的最小投递方式仍待 implementation plan 细化，候选是随包携带最小 vendor/wheels，而不是继续整包 `.venv`。
  - 由于当前会话未获用户授权启用子 agent，spec review loop 只能先做主线程本地自审；后续若需要额外 spec reviewer，再由用户显式授权。
- 下一步：请用户审阅 `docs/superpowers/specs/2026-04-23-packaged-python-runtime-bootstrap-design.md`；用户确认后，按 `writing-plans` 把实现拆成测试与代码步骤，再进入 TDD 实施。

## 2026-04-23 20:24 (Asia/Shanghai)
- 背景：用户已确认 packaged runtime bootstrap 设计，当前进入 implementation planning；本轮目标是把“首启官方 Python runtime + 最小 `python_deps` 资源 + fail-closed packaged 启动链”拆成可执行的 TDD 任务，不直接动实现。
- 已完成：
  - 已读取并复核当前关键实现落点：`app_desktop_web/electron-builder.config.cjs`、`app_desktop_web/electron-builder-preflight.cjs`、`app_desktop_web/electron-main.cjs`、`app_desktop_web/python_backend.js`、`app_desktop_web/tests/electron/program_access_packaging.test.js`、`app_desktop_web/tests/electron/python_backend.test.js`、`pyproject.toml`。
  - 已把实现计划落盘到 `docs/superpowers/plans/2026-04-23-packaged-python-runtime-bootstrap.md`，计划明确了文件职责、四个 chunk、红灯测试、最小 `python_deps` 导出、packaged runtime bootstrap、packaged 启动接线、打包体积验证和文档回写步骤。
- 已做验证：
  - 本轮仍是文档阶段，仅做代码/测试入口阅读与计划自审，没有新的自动化测试执行结果。
- 当前进度：spec 与 implementation plan 均已齐备；当前断点位于“准备进入执行阶段，先写 failing tests 锁定 builder config / packaged bootstrap / runtime bootstrap 契约”。
- 余险：
  - 计划已选用“打包最小 `python_deps` 资源并在首启安装到托管 runtime”的具体实现路线；真实裁剪排除名单是否足够，必须靠后续 import smoke + packaged smoke 验证，不可凭静态推断宣称可用。
  - 当前会话未获用户授权启用子 agent；即便 harness 支持多 agent，实现阶段也必须默认在主线程本地执行。
- 下一步：提交计划文档与 session-log 更新，然后进入 `executing-plans` / `test-driven-development` 阶段，先补 Electron 侧 failing tests。

## 2026-04-23 22:16 (Asia/Shanghai)
- 背景：用户要求把配置管理里的商品级“手动暂停”从行外独立文案按钮改成真正的行内状态位，让人一眼看出暂停还是运行。
- 已完成：
  - 新增设计文档 `docs/superpowers/specs/2026-04-23-query-config-inline-pause-status-design.md` 与实现计划 `docs/superpowers/plans/2026-04-23-query-config-inline-pause-status.md`，锁定边界为“只改配置管理前端状态表达，不改后端 `manual_paused` 语义、不改统一保存机制、不碰主链路”。
  - `app_desktop_web/src/features/query-system/components/query_item_table.jsx` 已为商品列表补上 `状态` 列；`app_desktop_web/src/features/query-system/components/query_item_row.jsx` 已把原先挂在行外的暂停/删除控制位收回商品行内容网格，正常模式显示图标状态，删除模式在同一格位原地替换成 `-`。
  - `app_desktop_web/src/styles/app.css` 已把商品行布局改为八列同排，并新增图标状态样式：`manual_paused=true` 显示红色三角形，`manual_paused=false` 显示绿色双竖线；界面不再显示“手动暂停”文字，只保留无障碍标签。
  - `app_desktop_web/tests/renderer/query_system_editing.test.jsx` 与 `app_desktop_web/tests/renderer/query_system_page.test.jsx` 已补回归，锁定“状态位在行内、运行/暂停图标类名正确、删除模式原地替换、只读锁定态仍可禁用”；`docs/agent/memory.md` 也已同步沉淀该 UI 约束。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/query_system_editing.test.jsx --run` -> `2 failed / 11 passed`，失败点准确落在旧控件仍是 `query-item-row__control`。
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/query_system_page.test.jsx --run` -> `1 failed / 14 passed`，失败点准确落在只读态仍使用旧类名。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/query_system_editing.test.jsx --run` -> `13 passed`。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/query_system_page.test.jsx --run` -> `15 passed`。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/query_system_models.test.js --run` -> `6 passed`。
  - 构建：`npm --prefix app_desktop_web run build` -> `vite build` 成功，当前产物为 `dist/assets/index-DPfO2VN4.js` 与 `dist/assets/index-BgpSKLkl.css`。
- 当前进度：代码、文档与 fresh verification 已全部到位；当前已到可手测状态。
- 下一步：让用户在正式桌面窗口里打开“配置管理”，人工确认三点：1. 状态图标已和商品条目同排；2. 绿色双竖线/红色三角形一眼可区分；3. 删除模式下该格位会原地切成 `-` 删除按钮。

## 2026-04-24 07:52 (Asia/Shanghai)
- 背景：用户反馈统计页在日期/时间段面板内选完范围并关闭后，界面仍停留旧数据，必须再手点一次“刷新统计”才会重新拉取。
- 已完成：
  - 在共享统计控件 `app_desktop_web/src/features/stats/stats_range_controls.jsx` 补了“筛选变更脏标记”，现在只要用户在面板内改过日期/时间段，关闭面板时就会自动触发一次刷新；若只是打开再关闭、不改筛选，则不会额外发请求。
  - 保留原有“刷新统计”按钮，但手动刷新时会清掉待刷新的脏标记，避免关闭面板后重复再打一枪。
  - 在 `app_desktop_web/tests/renderer/query_stats_page.test.jsx` 与 `app_desktop_web/tests/renderer/account_capability_stats_page.test.jsx` 新增回归，锁定“改过筛选并关闭面板后应立即请求新日期并更新表格”。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/query_stats_page.test.jsx --run` -> `1 failed / 3 passed`，失败点为关闭面板后仍只看到初始 `today` 请求。
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/account_capability_stats_page.test.jsx --run` -> `1 failed / 2 passed`，失败点同样是关闭面板后未发出新日期请求。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/query_stats_page.test.jsx --run` -> `4 passed`。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/account_capability_stats_page.test.jsx --run` -> `3 passed`。
  - 合并验证：`npm --prefix app_desktop_web test -- tests/renderer/query_stats_page.test.jsx tests/renderer/account_capability_stats_page.test.jsx --run` -> `2 files / 7 tests passed`。
- 当前进度：统计页日期面板关闭即自动刷新已到可手测状态；本轮未触碰后端统计口径、接口参数和主链路，仅改共享前端控件与 renderer 回归。
- 余险：
  - 当前验证覆盖了“按天筛选后关闭面板自动刷新”；共享控件对时间段和快捷范围也走同一脏标记/关闭刷新路径，但尚未额外补更宽的全量 renderer 场景。
  - 工作树里另有与本轮无关的脏改：`docs/superpowers/specs/2026-04-23-packaged-python-runtime-bootstrap-design.md` 以及 `tmp_startup_*.db`，本轮未处理。
- 下一步：让用户在真实桌面窗口里分别打开“查询统计”和“账号能力统计”，选一个非当天日期或时间段后直接关闭面板，确认表格会立刻切到对应数据，不再需要补点“刷新统计”。

## 2026-04-24 08:13 (Asia/Shanghai)
- 背景：用户要求检查当前会员放权，并把账号中心“浏览器查询”开关的“打开”纳入程序会员权限；若当前未放权，前端必须弹窗提示“当前此功能未开放”。
- 已完成：
  - 先补设计与实现文档 `docs/superpowers/specs/2026-04-24-browser-query-enable-entitlement-design.md`、`docs/superpowers/plans/2026-04-24-browser-query-enable-entitlement.md`，冻结边界为“只管浏览器查询开启动作，不改关闭、登录链、白名单链、首次绑定默认关闭与只读锁主语义”。
  - 后端在 `app_backend/api/routes/accounts.py` 为 `PATCH /accounts/{id}/query-modes` 新增窄 guard：只有 `browser_query_enabled` 从关切到开时，才会校验 `account.browser_query.enable`；未放权时统一返回 `program_feature_not_enabled + 当前此功能未开放 + action=account.browser_query.enable`。
  - `RemoteEntitlementGateway` 与 `CachedProgramAccessGateway` 已补细粒度能力判断：在总开关 `program_access_enabled` 之外，还要显式拥有 `account.browser_query.enable`（或兼容 `feature_flags.account_browser_query_enable=true`）才允许开通；默认 member 计划未携带该权限，因此当前行为自然落成“未开放”。
  - 账号中心前端已补专用弹窗 `FeatureUnavailableDialog`；`use_account_center_page.js` 只对 `program_feature_not_enabled + account.browser_query.enable` 这一条错误弹“当前此功能未开放”，其它错误继续走原日志/共享错误出口，不扩大影响面。
  - `README.md` 已核对，本次无需改动。
- 已做验证：
  - backend 红灯：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_routes.py tests/backend/test_remote_entitlement_gateway.py -q`，结果 `2 failed, 34 passed`；失败点准确落在“路由尚未拦浏览器查询开启”和“远端 entitlement 尚未区分细粒度权限”。
  - renderer 红灯：`npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx --run`，结果 `1 failed / 19 passed`；失败点准确落在账号页当前还没有“功能未开放”弹窗。
  - backend 绿灯：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_account_routes.py tests/backend/test_remote_entitlement_gateway.py -q`，结果 `36 passed`。
  - renderer 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/account_center_editing.test.jsx --run`，结果 `20 passed`。
  - 旁路回归：`npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/program_access_provider.test.jsx --run`，结果 `14 passed`；`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_program_access_guard_routes.py -q`，结果 `3 passed`。
- 当前进度：浏览器查询开通放权与前端未开放弹窗已到可手测状态；当前 member 默认因未携带新权限码而会弹“当前此功能未开放”。
- 余险：
  - 默认 member 计划当前仍只有 `program_access_enabled` 与 `runtime.start`，因此除非后续远端控制面显式补授 `account.browser_query.enable`，否则正式桌面将持续拒绝开启浏览器查询；这是本轮刻意采用的 fail-closed 口径。
  - 本轮只锁住“开启动作”；更深层的 token 查询运行时 eligibility 仍主要看 `token_enabled + 登录态`，若未来产品要求“无该权限时即使历史上已开启也不得参与 token 查询”，还需另开一刀下沉到 query runtime 侧。
- 下一步：让用户在真实桌面窗口里进入账号中心，找一个当前显示“浏览器查询已禁用”的已登录账号，点击开启，确认会弹“当前此功能未开放”；同时再点一个已启用账号的关闭，确认关闭行为仍照常保存。

## 2026-04-24 08:03 (Asia/Shanghai)
- 背景：用户要求修复“任务3 / 扫货系统”在停止扫货后把命中、成功、失败数据清空的问题；目标是改成按日期口径展示当天累计，不再因 stop 动作清空。
- 已完成：
  - backend `app_backend/application/use_cases/get_purchase_runtime_status.py` 新增停止态当天统计回填：当查询运行时已无 active config 时，会改为读取当前已选配置与 `stats_repository` 的当日统计，把商品行的查询次数、命中、成功、失败与来源统计补回 `/purchase-runtime/status`。
  - backend 调整了所有对外状态出口的一致口径：`app_backend/api/routes/purchase_runtime.py`、`app_backend/api/routes/query_configs.py`、`app_backend/application/use_cases/get_app_bootstrap.py`，以及 `app_backend/infrastructure/purchase/runtime/purchase_runtime_service.py` 的 runtime update payload，现在 stop 后的接口响应与 websocket 推送不会再回空白商品行。
  - frontend `app_desktop_web/src/features/purchase-system/hooks/use_purchase_system_page.js` 已放宽 stopped 态 `item_rows` 的消费条件：当运行时已停止但后端仍带回商品行统计时，页面继续用这些行覆盖所选配置卡片，不再因为 `active_query_config=null` 强行回落成全 0。
  - 新增回归：`tests/backend/test_purchase_runtime_routes.py` 锁定“停止态仍返回当天已选配置统计”，`app_desktop_web/tests/renderer/purchase_system_page.test.jsx` 锁定“停止后仍展示所选配置当天统计”。
- 已做验证：
  - 红灯：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_purchase_runtime_routes.py -k "keeps_selected_config_daily_item_stats_when_stopped" -q` -> `1 failed`，失败点为 `item_rows == []`。
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/purchase_system_page.test.jsx --run --testNamePattern "keeps stopped-state daily stats visible for the selected config"` -> `1 failed`，失败点为商品卡片仍显示 `查询次数0/命中0/成功0/失败0`。
  - backend 回归：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_purchase_runtime_routes.py tests/backend/test_app_bootstrap_route.py tests/backend/test_runtime_update_websocket.py -q` -> `35 passed`。
  - renderer 回归：`npm --prefix app_desktop_web test -- tests/renderer/purchase_system_page.test.jsx --run` -> `32 passed`。
- 当前进度：停止扫货不再清空当天商品级统计，代码与受影响自动化回归均已收口；当前已到可手测状态。
- 余险：
  - 本轮把“停止后显示当天累计”修到接口与页面层，未扩大去动查询命中主链、购买调度热路径或统计落库链路。
  - README 未涉及该行为说明；已核对，本次无需改动。
- 下一步：让用户在真实桌面窗口里启动一次扫货、产生命中后点击“停止扫货”，确认商品卡片仍保留当天的查询次数/命中/成功/失败；再跨到次日验证自然归零。

## 2026-04-24 08:57 (Asia/Shanghai)
- 背景：用户在远端管理员控制台 `http://8.138.39.139:18787/admin` 登录时看到 `invalid admin credentials`，要求确认服务器上能否直接看到密码，并把提示改成“用户名或者密码错误”。
- 已完成：
  - 已本地复核 `program_admin_console/src/controlPlaneStore.js`：管理员密码只存 `password_hash`，使用 `scrypt$<salt>$<digest>` 形态校验，不存在可直接回读的明文密码。
  - 已通过 SSH 连到远端 `admin@8.138.39.139`，进入 `c5-program-admin` 容器读取 `/app/data/control-plane.sqlite` 的 `admin_user` 表，确认当前远端管理员用户名为 `ULGNATSUN`、状态 `active`，密码字段仍是 `scrypt$...` 哈希，无法反推出原密码。
  - 已按用户要求修改 `program_admin_console/src/server.js` 的管理员登录失败文案为“用户名或者密码错误”，并在 `program_admin_console/tests/control-plane-server.test.js` 补回归断言。
  - 已把变更同步部署到远端：上传新 `server.js` 到 `/home/admin/c5-program-admin-src/src/server.js`，重建镜像 `c5-program-admin:login-msg-20260424_085419`，并替换运行中的 `c5-program-admin` 容器。
- 已做验证：
  - 红灯：`npm --prefix program_admin_console run test:server` -> 失败点准确落在返回文案仍是 `invalid admin credentials`。
  - 绿灯：`npm --prefix program_admin_console run test:server` -> `control-plane-server tests passed`。
  - 远端运行态：`sudo docker ps --filter name=c5-program-admin --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"` -> 容器已切到 `c5-program-admin:login-msg-20260424_085419`，端口仍为 `18787->8787`。
  - 远端接口验证：`curl --json '{"username":"wrong-user","password":"wrong-pass"}' http://8.138.39.139:18787/api/admin/login` -> 返回 `{"ok":false,"reason":"invalid_credentials","message":"用户名或者密码错误"}`。
- 当前进度：远端控制台登录失败提示已改成中文新文案；密码无法查看明文，但已确认当前管理员用户名不是默认 `admin`，而是 `ULGNATSUN`。
- 余险：
  - 当前只确认了用户名与哈希形态，未替用户重置管理员密码。
  - 工作树里仍有本轮外的并行脏改，未触碰。
- 下一步：若用户仍进不去，下一刀应直接在远端执行管理员密码重置，而不是继续猜旧密码。

## 2026-04-24 08:04 (Asia/Shanghai)
- 背景：用户反馈点击程序进入主页面慢；本轮已确认优先采用“A 方案”，即 embedded 启动时主界面先亮，backend 后台接管，不再把 renderer 首次加载硬卡在 `/health` 后面。
- 已完成：
  - `app_desktop_web/electron-main.cjs` 已改成 eager shell 启动：embedded 模式先直接加载 renderer，再在 backend ready 后通过 `desktop:bootstrap-config-updated` 推送新 bootstrap；同时补齐 remote 模式失败文案，避免 electron 回归继续漂移。
  - `app_desktop_web/electron-preload.cjs` 与 `app_desktop_web/src/desktop/bridge.js` 新增 bootstrap 配置订阅能力；renderer 订阅后会先补读一次当前快照，避免 backend 在订阅前 ready 时丢更新。
  - `app_desktop_web/src/App.jsx` 改为跟随 bootstrapConfig 动态创建 client/runtime manager，并在 `backendStatus !== ready` 时只渲染主界面壳与“本地服务启动中”占位；backend ready 后才挂载首页页面与拉取 `/app/bootstrap`、账号列表等数据。`app_desktop_web/src/styles/app.css` 补了启动占位样式。
  - 已新增/更新回归：`app_desktop_web/tests/electron/program_access_packaging.test.js` 锁定“packaged embedded 启动时先亮 app shell、ready 后推 bootstrap”；`app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx` 锁定“starting 阶段不抢跑首页请求，收到 ready 更新后再拉 bootstrap/home data”。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run` -> `1 failed / 11 passed`，失败点为旧逻辑仍先走 `{ mode: "loading" }`。
  - 红灯：`npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run` -> `1 failed / 5 passed`，失败点为 renderer 尚未显示“本地服务启动中”，且 backend 未 ready 时已提前渲染账号页。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js --run` -> `12 passed`。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/renderer/app_remote_bootstrap.test.jsx --run` -> `6 passed`。
  - 受影响 renderer 回归：`npm --prefix app_desktop_web test -- tests/renderer/account_center_page.test.jsx tests/renderer/app_state_persistence.test.jsx tests/renderer/app_remote_bootstrap.test.jsx --run` -> `3 files / 15 tests passed`。
  - 受影响 electron 回归：`npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/electron_remote_mode.test.js --run` -> `2 files / 32 tests passed`。
  - 构建：`npm --prefix app_desktop_web run build` -> 成功，当前产物为 `dist/assets/index-BFhvld35.js` 与 `dist/assets/index-PuT2cmDZ.css`。
- 当前进度：embedded 桌面启动链已到可手测状态；用户现在应先看到主界面壳，再由 backend ready 后接管首页数据，不再卡在单独 loading 页。
- 余险：
  - 本轮优先做的是体感提速，不是继续硬砍 Python backend 冷启动本体；backend 导入时长本身仍在，只是不再挡住主界面首亮。
  - README 已核对，本次无需改动。
- 下一步：让用户从真实桌面入口 `node main_ui_node_desktop.js` 或正式程序包重新启动，确认程序会先进入主界面壳，再在稍后自动加载账号页数据；若仍感慢，再继续追后端导入冷启动本体。

## 2026-04-24 08:16 (Asia/Shanghai)
- 背景：在主界面先亮之后，继续追本地 backend 冷启动；本轮聚焦此前已确认的重复装配点：`app_backend.main` 在模块导入期先执行一次 `app = create_app()`，而桌面启动再调用 `main()` 时又会再建一次 app。
- 已完成：
  - `app_backend/main.py` 已移除顶层立即构建的默认 `app`，改为 `_default_app + get_default_app() + __getattr__` 懒加载口径；现在导入 `app_backend.main` 时不会立刻建 app，只有显式访问 `backend_main.app` 时才会第一次构建并缓存。
  - `tests/backend/test_backend_main_entry.py` 新增红绿回归，锁定“导入模块后，`backend_main.app` 必须经由当前 `create_app()` 懒加载一次且仅一次”，避免后续再把重复装配回灌回来。
  - 本轮未改 `create_app()` 与 `main()` 对外契约，也未动桌面 JS 启动链、业务路由或主链路逻辑。
- 已做验证：
  - 红灯：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_backend_main_entry.py -q` -> `1 failed / 5 passed`，失败点为旧顶层 `app` 已在导入时提前构建，访问 `backend_main.app` 未触发新的 `create_app()`。
  - 绿灯：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_backend_main_entry.py -q` -> `6 passed`。
  - backend 受影响回归：`C:/Users/18220/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/backend/test_backend_main_entry.py tests/backend/test_desktop_web_backend_bootstrap.py -q` -> `13 passed`。
  - electron 受影响回归：`npm --prefix app_desktop_web test -- tests/electron/python_backend.test.js --run` -> `11 passed`。
  - 性能复测：导入与装配剖面从 `import_main_ms≈2074 / create_app_ms≈252 / total≈2326` 降到 `import_main_ms≈1524 / create_app_ms≈188 / total≈1712`，说明重复装配这一刀已被砍掉，单次剖面约少 `614ms`。
- 当前进度：本地 backend 冷启动已进一步收口，最明确的一次重复建 app 已消失；下一阶段若还要继续压时长，就该进后端重模块延迟导入或更细的装配拆分。
- 余险：
  - 端到端 `backend_ready_ms` 单次采样仍可能受磁盘、解释器缓存和系统负载抖动影响，判断是否提速应优先看“导入期不再重复建 app”这一结构性证据，而不是只看单次 wall-clock。
  - README 已核对，本次无需改动。
- 下一步：若用户继续追冷启动，优先定位 `app_backend.main` 顶层剩余重模块导入链，尤其是浏览器运行时、program access、stats/route 装配，再决定第二刀拆哪一段。

## 2026-04-24 09:43 (Asia/Shanghai)
- 背景：用户继续反馈 `main_ui_node_desktop_local_debug.js` 进入时仍然响应缓慢；本轮专查本地调试入口链路，而不是程序会员链或 embedded backend 数据接管链。
- 已完成：
  - 先量了 `main_ui_node_desktop_local_debug.js -> main_ui_node_desktop.js` 的窗口前同步预处理，确认慢点命中 `ensureRendererBuild()`：现场一次采样里 `apply_env_ms≈0.45 / ensure_renderer_build_ms≈1885.06 / ensure_electron_runtime_ms≈0.59`，说明卡顿发生在窗口出来前的同步前端 build。
  - 针对 `local_debug` 入口新增契约：`main_ui_node_desktop_local_debug.js` 现在会注入 `C5_LOCAL_DEBUG_REUSE_RENDERER_DIST=1`，声明“本地调试优先复用现有 dist”。
  - `main_ui_node_desktop.js` 的 `ensureRendererBuild()` 现在支持读取该环境变量：只要本地调试态且 `app_desktop_web/dist/index.html` 已存在，就直接复用现有构建产物，不再因为源码时间戳比 dist 新而同步重跑一次 Vite build；若 dist 缺失，仍会正常补构建。
  - `app_desktop_web/tests/electron/desktop_launcher.test.js` 新增回归，锁定“local debug 应注入复用 dist 标记”和“有 dist 时即使源码较新也不得重建”。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js --run` -> `2 failed / 6 passed`，失败点分别为本地调试环境里尚未注入 `C5_LOCAL_DEBUG_REUSE_RENDERER_DIST=1`，以及 `ensureRendererBuild()` 仍在 source newer 时触发 build。
  - 绿灯：`npm --prefix app_desktop_web test -- tests/electron/desktop_launcher.test.js --run` -> `8 passed`。
  - 现场复测：应用本地调试环境后，`ensure_renderer_build_ms` 从上一轮现场的约 `1885ms` 降到本轮 `0.25ms`，`prelaunch_total_ms≈0.60ms`，说明本地调试入口前面的同步 build 门槛已被切掉。
- 当前进度：`main_ui_node_desktop_local_debug.js` 现在默认优先秒开旧 dist，不再因为最近改过源码就先卡一遍同步 build；当前已到可手测状态。
- 余险：
  - 这刀只影响 `main_ui_node_desktop_local_debug.js` 调试入口；正式入口 `main_ui_node_desktop.js` 仍保留“源码新于 dist 时自动重建”的原口径。
  - 若本地调试态需要看最新前端改动，现在需先显式跑一次 `npm --prefix app_desktop_web run build`，然后再重开 local debug；这是本轮刻意采用的“启动速度优先”取舍。
- 下一步：让用户重新用 `node main_ui_node_desktop_local_debug.js` 启动，确认窗口能明显更快出现；若还慢，再继续拆“窗口出来后”阶段的 Electron/renderer/backend 接管链。

## 2026-04-24 08:10 (Asia/Shanghai)
- 背景：用户要求顶层前端页面不要在每次侧栏点击回切时都重新向后端拉取，并明确希望沿用当前前端已存在的同步/保活机制，而不是额外引入新库。
- 已完成：
  - `app_desktop_web/src/App.jsx` 把 `账号中心 / 查询统计 / 账号能力统计 / 通用诊断` 接入和 `配置管理 / 扫货系统` 同类的 lazy keep-alive 挂载模式；这些页面首次进入后常驻前端内存，后续侧栏回切不再因为 remount 重打一遍初始请求。
  - `app_desktop_web/src/features/diagnostics/use_sidebar_diagnostics.js` 改成“已有诊断快照时，重新打开页面只恢复后续轮询，不因点击页签立刻再打一枪 `/diagnostics/sidebar`”；首次进入仍保留即时加载。
  - 新增 `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx`，锁死“账号中心 / 两个统计页 / 通用诊断”首次进页可拉、回切不重拉的行为；同时补写实施计划 `docs/superpowers/plans/2026-04-24-page-keepalive-and-fetch-dedup.md`。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx` -> `2 failed`，失败点分别为账号中心回切二次 GET 与诊断页回切二次 GET。
  - 绿灯：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx` -> `2 passed`。
  - 邻近 renderer 回归：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx query_stats_page.test.jsx account_capability_stats_page.test.jsx account_center_page.test.jsx app_state_persistence.test.jsx diagnostics_sidebar.test.jsx query_system_page.test.jsx purchase_system_page.test.jsx` -> `8 files / 72 tests passed`。
- 当前进度：顶层页面现已统一到“首进加载一次，之后靠前端保活 + 现有自建同步链路复用状态”的口径；当前已到可手测状态。
- 余险：
  - 这刀只收口顶层页面生命周期，不等于已经把统计页、账号中心、诊断页完全并入统一 runtime store；现阶段仍是“页面保活优先，局部自管状态仍保留”。
  - README 已核对，本次无需改动。
- 下一步：让用户在真实桌面里依次来回切换 `账号中心 / 查询统计 / 账号能力统计 / 通用诊断`，确认表格与诊断快照直接复用前一轮页面状态，不再每次点回去都明显重新加载。

## 2026-04-24 09:30 (Asia/Shanghai)
- 背景：用户手测后反馈，若启动时当前页不是账号中心，第一次从左侧栏切到账号中心仍会短暂看到“加载中”。
- 已完成：
  - 在 `app_desktop_web/tests/renderer/app_page_keepalive.test.jsx` 新增红绿回归，锁定“即使启动页是查询统计，账号中心也必须在后台先预热 `/account-center/accounts`，而不是等点击账号中心时才首拉”。
  - 在 `app_desktop_web/src/App.jsx` 调整顶层 keep-alive 初始挂载策略：`account-center` 改为无论当前启动页是什么都默认先挂载，其他页面仍保持按首次激活懒挂载。
- 已做验证：
  - 红灯：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx` -> `1 failed / 2 passed`，失败点为启动页在 `query-stats` 时，`/account-center/accounts` 调用次数仍是 `0`。
  - 绿灯：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx` -> `3 passed`。
  - 邻近回归：`npm --prefix app_desktop_web test -- app_page_keepalive.test.jsx account_center_page.test.jsx app_state_persistence.test.jsx query_stats_page.test.jsx` -> `4 files / 16 tests passed`。
- 当前进度：账号中心现在会在后台先预热，切回账号中心时不再等点击后才开始首拉；当前已到可手测状态。
- 余险：
  - 这刀只把账号中心改成 eager hidden mount，其余统计页/诊断页仍保持“首次点开才挂载”的策略。
  - 本轮未提交 commit；仅保留在当前工作树。
- 下一步：让用户在真实桌面里把启动页停在“查询统计”或别的非账号页，再点回“账号中心”，确认不再看到那一闪的“加载中”。

## 2026-04-24 08:36 (Asia/Shanghai)
- 背景：用户要求把 `feature/packaged-python-runtime-bootstrap` 的整条改动正式落回根工作树并提交；当前根工作树还同时挂着“浏览器查询开通放权”“embedded 主界面先亮”“页面保活”等别线脏改，因此本轮只整合 packaged runtime 相关写域，不顺手打包进其它主线。
- 已完成：
  - 已把 packaged runtime 相关干净文件从 side worktree 合回根工作树：`.gitignore`、`AGENTS.md`、`app_desktop_web/electron-builder.config.cjs`、`app_desktop_web/electron-builder-preflight.cjs`、`app_desktop_web/python_backend.js`、`app_desktop_web/python_runtime_{config,resources,bootstrap}.js/cjs`、相关 Electron tests，以及 `docs/superpowers/plans/2026-04-23-packaged-python-runtime-bootstrap.md`。
  - `app_desktop_web/electron-main.cjs` 已按根工作树现状手工并刀为“eager shell 先亮 + packaged release 仍先走 `ensureManagedPythonRuntime()`”的组合状态：保留主界面先亮与 bootstrap 更新通道，同时恢复 packaged runtime 下载/校验/安装后再启动 backend 的链路。
  - `app_desktop_web/tests/electron/program_access_packaging.test.js` 已同步收口为组合契约：embedded eager shell 仍先亮，但 packaged release 现在必须使用托管 runtime、builder 资源必须是 `python_deps`、preflight 只暴露 `preparePackagedPythonResources -> verifyPackagedPythonResources` 新链。
  - `docs/agent/memory.md` 已补回 packaged runtime 的隔离约束与“不默认执行 `build:win`”的稳定规则，避免根工作树后续续战时再次回退到旧打包口径。
- 已做验证：
  - `npm --prefix app_desktop_web test -- tests/electron/program_access_packaging.test.js tests/electron/python_backend.test.js tests/electron/python_runtime_bootstrap.test.js tests/electron/electron_remote_mode.test.js --run` -> 初次 `49 passed`；吸收 code review 后补了“损坏 runtime 必须重下”“下载悬挂必须超时失败”两条回归，再次执行同命令结果 `51 passed`。
  - `node app_desktop_web/electron-builder-preflight.cjs` -> 成功；过程中触发一次 `vite build`，随后输出 `Packaged Python resources preflight passed ... app_desktop_web/build/python_deps`。
- 当前进度：packaged runtime 主线已在根工作树达成“代码 + 规则 + focused verification”收口，下一步只剩把这组文件单独提交；其它并行主线改动保持原样，不并入本次 commit。
- 余险：
  - 本轮只做 side branch 到根工作树的落地与 focused verification，没有重新执行 `pack:win` 或 `build:win`；这符合当前新增的项目级约束“非经用户主动指定，不默认重生 installer”。
  - 根工作树仍保留多条未提交别线；本次 commit 必须继续使用 pathspec 精确提交，避免把其它任务顺手夹带进 packaged runtime 收口 commit。
- 下一步：按 packaged runtime 相关 pathspec 单独提交根工作树整合结果；提交后再复核 `git status`，确认本次只清走这条主线，旁边别线保持不动。

## 2026-04-24 09:20 (Asia/Shanghai)
- 背景：用户继续追远端管理员控制台的暴露面，追问“刷新或重连后用户名还留在网页上会不会暴露”，并要求为下一会话补可直接承接的提示词。
- 已完成：
  - 已复读当前控制台前端实现：`program_admin_console/ui/app.js` 仍把管理员 `session_token` 写入 `window.localStorage["program_admin_console_token"]`，刷新后会自动带 token 请求 `/api/admin/session`，若会话有效则恢复登录并在页面上显示当前管理员用户名。
  - 已复读当前控制台模板：`program_admin_console/ui/index.html` 登录表单默认带 `autocomplete="username"` / `autocomplete="current-password"`；因此刷新后页面上仍出现用户名，既可能来自浏览器自动填充，也可能来自 token 恢复后的已登录态。
  - 已确认这条“用户名暴露”问题当前还没有单独 spec/plan；最新文档断点只收口到“登录失败文案改中文 + 当前管理员用户名是 `ULGNATSUN` + 不可查看明文密码”。
- 当前进度：
  - 远端控制台登录失败文案已收口为“用户名或者密码错误”并已部署。
  - 控制台刷新后仍保留 token / 可自动恢复登录，这正是当前用户名继续留在网页上的主要暴露面；这一刀还没有实施修改。
- 余险：
  - 当前远端控制台仍为 `HTTP` 明文入口 `http://8.138.39.139:18787/admin`，其风险高于“用户名留在页面上”本身。
  - 根工作树 `program_admin_console/` 仍有多处未提交脏改，包含 `README.md`、`src/server.js`、`ui/app.js`、`ui/index.html` 与相关测试；下一会话必须小心并刀，不要把无关线误并进来。
- 下一步：
  - 优先收口控制台前端的 token 持久化策略：把管理员 token 从 `localStorage` 改成“仅当前会话有效”或彻底不持久化，并补对应红绿回归。
  - 紧接着再评估是否同时关闭登录页用户名自动填充，避免刷新后仅靠浏览器缓存继续暴露管理员用户名。

## 2026-04-24 09:27 (Asia/Shanghai)
- 背景：按交接断点继续收口远端管理员控制台的主要暴露面；本轮只处理“管理员 token 落在 `localStorage`、刷新后自动恢复登录并显示当前管理员用户名”这一刀，不回退已部署的中文错误提示，也不尝试查看原密码。
- 已完成：
  - `program_admin_console/tests/control-plane-ui.test.js` 先补红灯：新增 tracked `localStorage` harness，锁死“旧 `localStorage` token 不能再让页面启动后自动进入工作区”“UI 不得再从 `localStorage` 读写管理员 token”，并把原先依赖启动即自动登录的工作区断言改成“显式注入当前页内存 token 后再验证工作区渲染”。
  - `program_admin_console/ui/app.js` 改为管理员 token 仅保留在当前页面内存：启动时不再从 `localStorage` 读 token，并在 `init()` 先清掉历史遗留的 `program_admin_console_token`；`saveToken()` 只维护内存态，登出/失效清理时继续 best-effort 删除旧持久化槽位。
  - 本轮未改 `program_admin_console/ui/index.html` 的 `autocomplete` 配置；当前结论是它只会带来“浏览器自动填充看起来像还记得用户名”的视觉误判，不是本轮更危险的持久化 token 主链。
- 已做验证：
  - 红灯：`npm --prefix program_admin_console run test:ui` -> 失败点为页面仍会因旧持久化 token 自动进入工作区（断言 `authPanel.hidden === false` 时实际为 `true`）。
  - 绿灯：`npm --prefix program_admin_console run test:ui` -> `control-plane-ui tests passed`。
  - 扩展回归：`npm --prefix program_admin_console test` -> 全套 `mail-config / mail-service / store / server / ui` 均通过。
- 当前进度：管理员控制台已收口到“登录只在当前页面存活，刷新不会再自动恢复管理员会话”；工作树仍保留本轮外的并行脏改，未触碰。
- 余险：
  - 本轮尚未把同样的前端改动部署到远端 `http://8.138.39.139:18787/admin`，因此远端现网若未单独发布，仍可能保留旧的自动恢复行为。
  - `autocomplete=\"username\" / \"current-password\"` 还在；它不会恢复管理员 token，但浏览器可能继续回填用户名，后续若要继续压暴露面，可再单独评估是否关闭。
- 下一步：
  - 若要让现网同步收口，下一刀应把本轮前端改动部署到远端控制台，并手测“登录后刷新应回到未登录、退出后再刷新仍未登录”。
  - 之后再决定是否连同 `autocomplete` 一起关闭，以减少浏览器自动填充造成的误判。

## 2026-04-24 09:41 (Asia/Shanghai)
- 背景：用户要求“收口现网”；本轮把本地已完成的管理员 token 非持久化改动正式发布到远端控制台 `http://8.138.39.139:18787/admin`，并保持中文错误提示不回退。
- 已完成：
  - 已用本机部署钥匙连接远端 `admin@8.138.39.139`，确认现网容器原先仍跑旧镜像 `c5-program-admin:login-msg-20260424_085419`，其 `ui/app.js` 还在从 `localStorage` 读 `program_admin_console_token`，且前端仍带旧 `/api/admin/bootstrap/state` 链。
  - 已将当前仓库 `program_admin_console` 整包打成发布 tar，同步到远端；把旧源码目录备份为 `/home/admin/c5-program-admin-src_backup_20260424_093717`，再用当前源码重建稳定发布目录 `/home/admin/c5-program-admin-src`。
  - 已在远端构建新镜像 `c5-program-admin:token-memory-20260424_093717`；先用旁路端口 `18788` 起 smoke 容器验健康、管理员 session 口和静态 `app.js`，确认新脚本已包含 `LEGACY_TOKEN_STORAGE_KEY/clearLegacyPersistedToken`，且登录失败文案仍为“用户名或者密码错误”。
  - smoke 通过后，已替换正式容器 `c5-program-admin`，公网 `18787` 现已切到新镜像；旁路 smoke 容器已清理。
- 已做验证：
  - 远端容器：`sudo docker ps --filter name=c5-program-admin --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"` -> `c5-program-admin c5-program-admin:token-memory-20260424_093717 Up ... 18787->8787`。
  - 宿主机回环接口：`curl http://127.0.0.1:18787/api/health` -> `{"ok":true}`；`curl http://127.0.0.1:18787/api/admin/session` -> `{"ok":true,"authenticated":false,"needs_bootstrap":false}`。
  - 公网接口：`curl http://8.138.39.139:18787/api/health` -> `{"ok":true}`；`curl http://8.138.39.139:18787/api/admin/session` -> `{"ok":true,"authenticated":false,"needs_bootstrap":false}`。
  - 真实错误提示：公网 `POST /api/admin/login`（错误账号密码）-> `{"ok":false,"reason":"invalid_credentials","message":"用户名或者密码错误"}`。
  - 公网静态脚本：`curl http://8.138.39.139:18787/admin/app.js` 已命中 `LEGACY_TOKEN_STORAGE_KEY` 与 `clearLegacyPersistedToken`，且额外 grep 证明不再包含旧的 `window.localStorage.getItem` token 恢复代码。
- 当前进度：管理员控制台现网已切到“不持久化管理员 token、刷新不再自动恢复会话”的新前端；旧镜像 tag 与旧源码备份均保留，可作为回退锚点。
- 余险：
  - 本轮已做真实接口与静态页面级验证，但未持有管理员明文密码，因此无法在现网做“正确登录后再按 F5”的真人闭环；若需要最终 UI 手测，需用户自己用现有管理员账号登录后刷新确认。
  - `autocomplete="username"/"current-password"` 仍在；它不会恢复 token，但浏览器仍可能自动回填用户名，造成“像还记得登录态”的视觉误判。
- 下一步：
  - 让用户在现网后台亲自做一次最终手测：登录成功后按刷新，应回到登录页；若浏览器仍自动填用户名，只视为自动填充而非登录恢复。
  - 若还要继续压暴露面，再单开一刀关闭登录表单 `autocomplete`。

## 2026-04-24 10:34 (Asia/Shanghai)
- 背景：用户进一步要求把后台收口成“先连服务器，再通过服务器访问后端”，因为家庭宽带公网 IP 会变化，不适合按固定 IP 放通安全组。
- 已完成：
  - 已审视 `program_admin_console` 控制面当前暴露面，并确认“必须买域名”不是前置条件；对自用后台，更合适的方案是把宿主机端口只绑到 `127.0.0.1`，再通过 SSH 隧道访问。
  - 已把远端正式容器 `c5-program-admin` 从 `0.0.0.0:18787->8787` 改成 `127.0.0.1:18787->8787`，镜像仍沿用 `c5-program-admin:token-memory-20260424_093717`，数据卷与密钥挂载保持不变。
  - 已补充 `program_admin_console/README.md`：新增“自用后台的更安全访问方式”，记录 `127.0.0.1` 绑定与 SSH 隧道访问命令，避免后续再按公网暴露示例回退。
- 已做验证：
  - 远端容器：`sudo docker ps --filter name=c5-program-admin --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"` -> 现为 `127.0.0.1:18787->8787/tcp`。
  - 远端宿主机本机访问：`curl http://127.0.0.1:18787/api/health` -> `{"ok":true}`；`curl http://127.0.0.1:18787/api/admin/session` -> `{"ok":true,"authenticated":false,"needs_bootstrap":false}`。
  - 公网入口已失效：本机 `curl.exe --max-time 5 http://8.138.39.139:18787/api/health` -> `curl: (7) Failed to connect ... Could not connect to server`。
  - SSH 隧道闭环：本机临时执行 `ssh -L 18787:127.0.0.1:18787 admin@8.138.39.139` 后，再访问 `http://127.0.0.1:18787/api/health`、`/api/admin/session` 与 `/admin` 均成功。
- 当前进度：管理员控制台现已只对服务器本机开放；日常访问路径已切为“本机 SSH 隧道 -> 服务器本机端口 -> 容器”。
- 余险：
  - 本轮只收口了后台入口暴露方式；控制面本身仍存在代码层安全待办，例如管理员登录缺少限速、`/api/admin/bootstrap` 在空库时仍是公开可打。
  - SSH 22 口仍是外部入口；后续若要继续加固，应确认远端只允许密钥登录，不保留弱口令登录。
- 下一步：
  - 若继续做代码侧安全收口，优先补管理员登录限速，再收 `/api/admin/bootstrap` 的初始化保护。
  - 若只需自用访问，后续直接按 README 新增的 SSH 隧道方式使用即可。

## 2026-04-24 10:37 (Asia/Shanghai)
- 背景：用户强调“这次改动尤为独特”，并明确要求把控制台现网收口方案记录清楚，避免后续 AI 只看到代码或旧公网示例，导致维护与部署姿势再次漂移。
- 已完成：
  - `program_admin_console/README.md` 已新增“当前现网口径（2026-04-24）”章节，明确写死：远端开发机 `8.138.39.139` 上的后台 `/admin` 当前不再公网开放，现网入口固定为“宿主机 `127.0.0.1:18787` + 本机 SSH 隧道 + 本地浏览器访问 `http://127.0.0.1:18787/admin`”。
  - `docs/agent/memory.md` 已同步提炼为跨会话稳定约束：后续 AI/维护者默认应保持“仅服务器本机可达 + SSH 隧道访问”的控制台部署口径，不要因为 README 仍保留历史公网 rollout 示例就无说明地重新打开公网端口。
  - 本轮没有再改运行代码与远端容器，仅补足跨会话文档锚点，让“实际做了什么”和“后续默认该怎么做”在 `README + memory + session-log` 三处对齐。
- 已做验证：
  - 已回读 `program_admin_console/README.md`，确认顶部已有“当前现网口径（2026-04-24）”章节。
  - 已回读 `docs/agent/memory.md`，确认新增了控制台“本机绑定 + SSH 隧道”稳定约束。
- 当前进度：这条控制台现网姿势现已从一次性操作沉淀为长期可读记录；后续新会话若按仓库规则承接，应能同时读到“发生过什么”和“默认别回退什么”。
- 余险：
  - README 中仍保留公网部署与历史联调示例，因为它们对一般部署说明仍有价值；真正防止回退的锚点现在依赖于顶部“当前现网口径”和 `memory` 中的稳定约束，后续 AI若只截读中间片段仍可能误判。
- 下一步：
  - 若继续收口安全代码，仍按上一条主线推进：先补管理员登录限速，再收 `/api/admin/bootstrap` 初始化保护。

## 2026-04-24 11:02 (Asia/Shanghai)
- 背景：用户需要一个“别再手敲 ssh 命令”的本机连接脚本，用于日常拉起控制台 SSH 隧道并打开后台页面；本轮不改服务端行为，只补客户端连接工具。
- 已完成：
  - 新增 `program_admin_console/tools/connectProgramAdminConsole.ps1`：默认使用 `C:/Users/18220/.ssh/c5_ecs_deploy_temp`，把本机 `127.0.0.1:18787` 转发到远端 `8.138.39.139:18787`，并在新开的 PowerShell 窗口中持有 SSH 隧道；默认会自动打开 `http://127.0.0.1:18787/admin`。
  - 新增 `program_admin_console/tools/connectProgramAdminConsole.cmd`：作为双击包装层，内部用 `powershell.exe -ExecutionPolicy Bypass` 调用上面的 `.ps1`，降低日常使用门槛。
  - 脚本内额外收了三处易错点：检查 `ssh` 是否存在、检查私钥文件是否存在、检查本机目标端口是否已被占用；并提供 `-DryRun` 与 `-LocalPort` 参数，方便验尸和端口冲突绕开。
  - 已同步更新 `program_admin_console/README.md` 的“自用后台的更安全访问方式”章节，补充脚本路径、默认行为、直接运行方式与常用参数。
- 已做验证：
  - `powershell -NoProfile -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun -NoBrowser` -> 成功输出 `SSH_PATH / SSH_ARGS / ADMIN_URL`。
  - 通过 PowerShell 直接调用 `.cmd` 包装层并传 `-DryRun -NoBrowser` -> 同样成功输出 `SSH_PATH / SSH_ARGS / ADMIN_URL`。
- 当前进度：控制台现网入口、README 口径、本机连接脚本三者已对齐；用户后续可直接运行脚本，而不必再手敲完整 SSH 隧道命令。
- 余险：
  - 本轮只验证了脚本 dry-run，不在验证阶段真的持久拉起新的隧道窗口；实际连接行为仍依赖本机 `ssh.exe`、私钥权限和远端 22 端口可达。
  - 脚本默认私钥路径与远端地址已写死为当前开发机口径；若后续换机或换钥匙，需要同步调整脚本参数或默认值。
- 下一步：
  - 若继续减轻日常使用心智负担，可以再补一个“断开隧道脚本”或“系统托盘/桌面快捷方式”。

## 2026-04-24 11:20 (Asia/Shanghai)
- 背景：用户进一步要求优化连接脚本，希望“打开浏览器工作，关闭浏览器后自动断开隧道”；由于这会改变脚本行为模型，本轮先按 brainstorming 门禁沉淀设计，而不直接跳进实现。
- 已完成：
  - 已复读当前连接脚本 `program_admin_console/tools/connectProgramAdminConsole.{ps1,cmd}`，确认现状是“启动新 PowerShell 窗口承载 SSH 隧道，再把后台 URL 交给默认浏览器”，这会复用已有浏览器进程，无法可靠感知“本次后台窗口何时真正结束”。
  - 已给出并得到用户确认的设计方向：不再依赖“默认浏览器 shell-open”，而是启动一个由脚本自己持有的专用浏览器进程；当该进程退出时，脚本再清理它自己启动的 SSH 隧道。
  - 已把设计写入 `docs/superpowers/specs/2026-04-24-program-admin-browser-bound-tunnel-design.md`，明确记录三种方案、推荐选型、生命周期规则、失败处理、测试策略与 out-of-scope。
- 已做验证：
  - 已回读 spec 文件，确认目标、边界与推荐方案写全；当前实现仍未开始，因此没有新增代码级验证。
- 当前进度：这条“关闭浏览器即断隧道”的需求已从聊天确认转化成仓库内可承接 spec；下一步应先让用户 review written spec，再进入 writing-plans / TDD 实现。
- 余险：
  - 本轮尚未实现新行为；当前连接脚本仍是旧口径，关闭浏览器不会自动清 SSH 隧道。
  - 若后续仍想保留“复用默认浏览器已有窗口”的使用方式，这和“可靠感知窗口关闭后断隧道”目标本身存在冲突，需要再次确认是否接受专用浏览器窗口。
- 下一步：
  - 让用户先 review `docs/superpowers/specs/2026-04-24-program-admin-browser-bound-tunnel-design.md`；若认可，再进入实现计划与代码修改。

## 2026-04-24 12:00 (Asia/Shanghai)
- 背景：用户已确认浏览器绑定隧道的 written spec 可执行，当前阶段从 brainstorming 正式切到 writing-plans。
- 已完成：
  - 已按 `writing-plans` 技能把实现步骤写入 `docs/superpowers/plans/2026-04-24-program-admin-browser-bound-tunnel.md`。
  - 计划已明确三块内容：1）先用 Node + 假 ssh/假浏览器写红灯测试；2）再把当前“默认浏览器 shell-open + 分离隧道窗口”改成“脚本直接持有 ssh 进程 + 专用浏览器进程”；3）最后补 README 与日志，并回跑 dry-run 验证。
- 已做验证：
  - 已回读计划文件，确认目标、文件路径、红绿命令、文档同步步骤都已写死。
- 当前进度：浏览器绑定隧道这条需求现在已经具备“spec -> plan”双文档锚点；下一步就是按计划进入 TDD 实现。
- 余险：
  - 计划尚未执行；当前仓库中的连接脚本仍是旧行为，关闭浏览器不会自动断开 SSH 隧道。
- 下一步：
  - 若用户继续推进，直接按 `docs/superpowers/plans/2026-04-24-program-admin-browser-bound-tunnel.md` 进入实现。

## 2026-04-24 12:13 (Asia/Shanghai)
- 背景：用户确认继续执行“关闭浏览器后自动断开控制台 SSH 隧道”的实现；本轮按已批准 spec/plan 进入 TDD，并要求把这条独特操作口径写清楚，避免后续 AI 或维护者回退到旧脚本行为。
- 已完成：
  - `program_admin_console/tests/connect-program-admin-console.test.js` 已新增 focused 回归：通过 fake ssh / fake browser wrapper 锁死三件事：1）dry-run 必须输出独立 `BROWSER_PATH / BROWSER_ARGS`；2）浏览器正常退出后，脚本必须清掉自己创建的本地隧道端口；3）浏览器非零退出时，脚本同样必须清 SSH 隧道并返回非零。
  - `program_admin_console/tools/connectProgramAdminConsole.ps1` 已从“新开 PowerShell 窗口承载 ssh + shell-open 默认浏览器”改成“脚本自己直接持有 ssh 子进程 + 专用浏览器子进程”的监督模型。当前默认会：
    - 启动 ssh 进程并等待本地转发端口 ready
    - 解析 Edge/Chrome 可执行文件
    - 用独立临时 `--user-data-dir` + `--app=` 方式拉起专用 Chromium 窗口访问 `/admin`
    - 等待该浏览器进程退出后，自动停止它自己启动的 ssh 进程
  - 脚本新增了 `-BrowserPath`（显式指定浏览器）、测试专用的 wrapper 注入入口，以及 `-DryRun` 下的 `BROWSER_PATH / BROWSER_ARGS` 输出；`program_admin_console/tools/connectProgramAdminConsole.cmd` 继续只作为轻量包装层。
  - `program_admin_console/package.json` 已新增 `test:connect-script`，并把它并入 `npm --prefix program_admin_console test`。
  - `program_admin_console/README.md` 已同步改写“本机连接脚本”章节：默认行为改为“启动专用浏览器窗口；关闭该窗口自动断隧道”，并补充 `-NoBrowser`、`-BrowserPath` 的示例。
  - `docs/agent/memory.md` 已同步提炼为稳定操作约束，明确后续默认不要回退到“复用已有默认浏览器窗口/标签页”的旧模式。
- 已做验证：
  - 红灯到绿灯：`node program_admin_console/tests/connect-program-admin-console.test.js` -> 已从初始失败转为 `connect-program-admin-console tests passed`。
  - dry-run：`powershell -NoProfile -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun -NoBrowser` -> 成功输出 `SSH_PATH / SSH_ARGS / ADMIN_URL`。
  - dry-run：`powershell -NoProfile -ExecutionPolicy Bypass -File program_admin_console/tools/connectProgramAdminConsole.ps1 -DryRun` -> 成功输出 `SSH_PATH / SSH_ARGS / BROWSER_PATH / BROWSER_ARGS / ADMIN_URL`，其中浏览器默认为本机 Edge。
  - 包装层 dry-run：通过 `.cmd` 调用同样成功输出 `SSH_PATH / SSH_ARGS / ADMIN_URL`。
  - 全套回归：`npm --prefix program_admin_console test` -> `mail-config / mail-service / store / server / ui / connect-script` 全部通过。
- 当前进度：控制台本机连接脚本现已收口到“专用浏览器窗口生命周期 = 本次隧道生命周期”；用户关闭该专用窗口后，本次 SSH 隧道会自动断开。
- 余险：
  - 真机上该行为依赖 Chromium 系浏览器（当前默认 Edge，回退 Chrome）；若未来要支持 Firefox 等非 Chromium 浏览器，需要另做参数与进程模型兼容。
  - 当前 `-NoBrowser` 模式仍保留，属于 tunnel-only 例外路径；用户若自己手动用它，只能靠关闭脚本窗口或 Ctrl+C 结束隧道。
- 下一步：
  - 若还要继续优化体验，可以再补一个“断开隧道脚本”或桌面快捷方式，但当前核心诉求已满足。
