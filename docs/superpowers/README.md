# Superpowers 文档说明

本目录下的 `specs/` 和 `plans/` 主要用于保留 2026-03-16 到 2026-03-18 这一轮重构过程记录。

当前仓库实际状态已经和这些历史文档里的很多“当时现状”不同：

- `autobuy.py` 目前保留在仓库中作为参考，但不属于默认运行链路
- `c5_layered` 已从仓库删除
- 当前运行入口是 `run_app.py -> app_frontend.main -> app_backend.main`

因此：

- 把这些文档当作迁移背景和设计推导记录来看
- 不要把文档里的旧文件路径、旧验证命令、旧未完成项当成当前代码现状
- 当前代码结构和运行入口，以根目录 `README.md` 与 `REFACTOR_EXECUTION_PLAN.md` 为准
