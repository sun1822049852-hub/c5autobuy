# 2026-04-21 Worktree Disposition Reference

## 目标

给当前仓库的 worktree 做一次“会员落地主线回收”视角的分拣，先判断哪些能删、哪些必须保留为回收源，避免再次从错误入口打包。

## 当前基线

- 唯一可信的桌面主线基线是根工作树 `master`，并保留 `main_ui_node_desktop.js` 作为主入口。
- 根工作树当前的未提交改动已包含会员 / 控制面 / 打包收口主线，剩余差距主要是烟测与 Windows 出包环境修复。
- 本清单已执行二轮清理：无关旧 worktree 已移除，`feature/membership-auth-v1` 也已判定为过期漂移源并删除。

## 分拣结果

说明：
- “偏离 master” 用 `master-only / branch-only` 表示。
- “可直接删除” 表示不会丢未提交代码；不代表必须马上删。

| Worktree | 最后提交时间 | 偏离 master | 当前状态 | 与会员落地关系 | 建议 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| `anti-bot-hardening-chunk1` | 2026-03-24 | `70 / 1` | clean | 无关 | 可直接删除 | 老分支、已干净、与当前会员主线回收无关。 |
| `feature/diagnostics-sidebar` | 2026-03-25 | `54 / 1` | clean | 无关 | 可直接删除 | 老分支、已干净、与当前会员主线回收无关。 |
| `feature/local-program-access-extension` | 2026-04-19 | `5 / 4` | dirty | 高 | 保留，作为回收源 | 这里有本地 `program_access` 骨架、只读守卫方向和桌面端接线；但它同时删除了真实入口链路并大范围改壳层，不能整枝合并，只能按模块择优回收。 |
| `feature/membership-auth-v1` | 2026-04-03 | `23 / 0` | dirty（已删除） | 中 | 已删除 | 该方向主要是本地多租户用户/会员模型，已与当前“本地共享工作区、远端统一鉴权”主语义漂移；审查确认其相对 `master` 已无提交级独占内容，故直接移除。 |
| `feature/program-control-plane-chunk1` | 2026-04-20 | `5 / 28` | dirty | 高 | 保留，作为回收源 | 远端控制面、SMTP、管理员后台、桌面端远端鉴权接线基本都在这里；但它把打包名改成了 `C5 账号中心`，也删改了主入口，必须拆件回收，不能直接拿来打包。 |
| `feat/purchase-competition-chunk3` | 2026-03-23 | `70 / 2` | clean | 无关 | 可直接删除 | 老分支、已干净、与当前会员主线回收无关。 |
| `purchase-page-ui-freeze` | 2026-03-21 | `81 / 0` | dirty（仅日志） | 无关 | 可直接删除 | 现场只剩未跟踪日志文件，没有会员相关代码价值。 |
| `remote-runtime-state-sync-exec` | 2026-04-03 | `25 / 2` | clean | 无关 | 可直接删除 | 与会员落地无直接关系，且工作树本身干净。 |
| `runtime-page-density-redesign` | 2026-03-20 | `89 / 2` | dirty（仅日志） | 无关 | 可直接删除 | 现场只剩未跟踪日志文件，没有会员相关代码价值。 |
| `stats-persistence-account-capability` | 2026-03-22 | `68 / 0` | clean | 无关 | 可直接删除 | 老分支、已干净、与当前会员主线回收无关。 |

## 已执行的清理结果

已从现场删除的无关旧 worktree：

- `anti-bot-hardening-chunk1`
- `feature/diagnostics-sidebar`
- `feat/purchase-competition-chunk3`
- `purchase-page-ui-freeze`
- `remote-runtime-state-sync-exec`
- `runtime-page-density-redesign`
- `stats-persistence-account-capability`
- `feature/membership-auth-v1`

当前仍保留的 worktree：

- `feature/local-program-access-extension`
- `feature/program-control-plane-chunk1`

## 会员回收顺序

1. 先以根工作树 `master` 为唯一落地主线，保持 `main_ui_node_desktop.js` 作为真实桌面入口。
2. 从 `feature/local-program-access-extension` 回收本地 Program Access 骨架与“只读可见、关键动作锁死”的守卫逻辑，但拒绝它对主入口和壳层的大范围漂移。
3. 从 `feature/program-control-plane-chunk1` 回收远端控制面、SMTP、后台 UI、远端 entitlement 接线与发行必需改动，但拒绝它的产品名/入口漂移。
4. `feature/membership-auth-v1` 已清理，不再作为会员落地参考源。

## 当前仍需保留的回收源

- `feature/local-program-access-extension`
- `feature/program-control-plane-chunk1`

以上两条仍有代码级脏改，在主线完成最终烟测与发行收口前不应删除。
