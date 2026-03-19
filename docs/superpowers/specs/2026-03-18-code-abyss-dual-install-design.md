# Code Abyss 双端部署设计

**日期：** 2026-03-18

**目标：** 在当前 Windows 机器上同时为 `Codex CLI` 与 `Claude Code` 安装 `code-abyss`，保留现有配置回滚能力，并验证核心安装结果。

## 背景

当前机器已经存在以下用户级配置目录：

- `C:/Users/18220/.codex/`
- `C:/Users/18220/.claude/`

这意味着本次操作不是全新安装，而是在现有配置上进行覆盖、合并与补充。安装对象是用户主目录下的全局 AI CLI 配置，而不是当前项目源码。

## 安装范围

### Codex CLI

计划通过官方安装器写入或更新以下内容：

- `C:/Users/18220/.codex/AGENTS.md`
- `C:/Users/18220/.codex/skills/`
- `C:/Users/18220/.codex/prompts/` 中自动生成的 prompts
- `C:/Users/18220/.codex/config.toml` 中新增或补齐的默认配置
- `C:/Users/18220/.codex/.sage-backup/`
- `C:/Users/18220/.codex/.sage-uninstall.js`

### Claude Code

计划通过官方安装器写入或更新以下内容：

- `C:/Users/18220/.claude/CLAUDE.md`
- `C:/Users/18220/.claude/output-styles/`
- `C:/Users/18220/.claude/skills/`
- `C:/Users/18220/.claude/settings.json`
- `C:/Users/18220/.claude/ccline/`
- `C:/Users/18220/.claude/.sage-backup/`
- `C:/Users/18220/.claude/.sage-uninstall.js`

此外，`Claude` 侧官方自动模式会尝试执行：

- `npm install -g @cometix/ccline@1`

## 方案选择

本次采用用户确认的 `官方满配双装` 方案：

1. 先手工备份关键现有配置，作为安装器备份机制之外的额外回滚点。
2. 使用 `code-abyss` 官方命令分别安装到 `Codex CLI` 与 `Claude Code`。
3. 对 `Claude` 侧允许安装 `ccline` 状态栏，保持与官方自动模式一致。
4. 安装完成后逐项验证配置文件、技能目录、prompts、状态栏与卸载脚本是否落盘。

## 风险与应对

### 风险

- 现有 `AGENTS.md`、`CLAUDE.md`、`skills/` 会被覆盖。
- `Claude` 的 `settings.json` 中 `outputStyle` 会切换为 `abyss-cultivator`。
- `Codex` 的 `config.toml` 会被补全默认项，并可能清理旧字段。
- 全局 npm 安装 `@cometix/ccline@1` 可能因网络、权限或 npm 环境异常失败。

### 应对

- 安装前做手工备份。
- 保留安装器生成的 `.sage-backup` 和 `.sage-uninstall.js`。
- 安装完成后即时验证，发现异常立即停止继续修改。

## 验证标准

安装完成后满足以下条件即视为成功：

1. `Codex` 与 `Claude` 两侧都生成安装器备份目录与卸载脚本。
2. `Codex` 侧存在新的 `AGENTS.md`、`skills/`、自动生成 prompts。
3. `Claude` 侧存在新的 `CLAUDE.md`、`output-styles/`、`skills/`。
4. `Claude` 的 `settings.json` 中 `outputStyle` 为 `abyss-cultivator`。
5. `ccline` 二进制或全局命令可被检测到。

## 说明

按用户要求，本次不进行任何 `git commit`、`git push` 或分支操作；设计文档仅落盘保存，不提交版本库。
