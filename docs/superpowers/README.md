# Superpowers 文档说明

本目录下的 `specs/` 和 `plans/` 主要用于保留 2026-03-16 到 2026-03-18 这一轮重构过程记录。

`references/` 用于保留对当前源码仍然有效的实现对账和排障参考。

当前仓库实际状态已经和这些历史文档里的很多“当时现状”不同：

- `autobuy.py` 目前保留在仓库中作为参考，但不属于默认运行链路
- `c5_layered` 已从仓库删除
- `app_frontend` 这套旧 `PySide6` UI 已从仓库删除
- 当前运行入口是 `run_app.py -> main_ui_account_center_desktop.js -> app_desktop_web/app_backend`

因此：

- 把这些文档当作迁移背景和设计推导记录来看
- 排查 legacy `autobuy.py` 与当前 backend 的语义漂移时，优先看 `references/2026-03-19-autobuy-backend-semantic-drift-reference.md`
- 不要把文档里的旧文件路径、旧验证命令、旧未完成项当成当前代码现状
- 当前代码结构和运行入口，以根目录 `README.md` 与 `REFACTOR_EXECUTION_PLAN.md` 为准
