# Code Abyss 双端部署 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前 Windows 机器上为 `Codex CLI` 和 `Claude Code` 执行 `code-abyss` 官方满配安装，并保留可验证的回滚点。

**Architecture:** 先在用户主目录下为两套现有配置做手工备份，再调用官方 `npx code-abyss` 安装命令分别落盘到 `~/.codex/` 与 `~/.claude/`。安装结束后使用文件检查和命令检查确认配置、技能、prompts、状态栏和卸载脚本全部就位。

**Tech Stack:** Windows PowerShell, Node.js, npm, npx, Code Abyss installer

---

## Chunk 1: 备份与环境确认

### Task 1: 创建手工回滚点

**Files:**
- Create: `C:/Users/18220/.codex-manual-backup-2026-03-18/`
- Create: `C:/Users/18220/.claude-manual-backup-2026-03-18/`
- Copy: `C:/Users/18220/.codex/AGENTS.md`
- Copy: `C:/Users/18220/.codex/config.toml`
- Copy: `C:/Users/18220/.claude/CLAUDE.md`
- Copy: `C:/Users/18220/.claude/settings.json`

- [ ] **Step 1: 复制 Codex 关键配置**

Run: `Copy-Item -Path "C:/Users/18220/.codex/AGENTS.md","C:/Users/18220/.codex/config.toml" -Destination "C:/Users/18220/.codex-manual-backup-2026-03-18" -Force`
Expected: 关键文件成功复制

- [ ] **Step 2: 复制 Claude 关键配置**

Run: `Copy-Item -Path "C:/Users/18220/.claude/CLAUDE.md","C:/Users/18220/.claude/settings.json" -Destination "C:/Users/18220/.claude-manual-backup-2026-03-18" -Force`
Expected: 关键文件成功复制

- [ ] **Step 3: 校验备份目录**

Run: `Get-ChildItem "C:/Users/18220/.codex-manual-backup-2026-03-18","C:/Users/18220/.claude-manual-backup-2026-03-18"`
Expected: 能看到刚复制的关键文件

## Chunk 2: 执行官方满配安装

### Task 2: 安装到 Codex CLI

**Files:**
- Modify: `C:/Users/18220/.codex/AGENTS.md`
- Modify: `C:/Users/18220/.codex/skills/`
- Modify: `C:/Users/18220/.codex/prompts/`
- Modify: `C:/Users/18220/.codex/config.toml`
- Create: `C:/Users/18220/.codex/.sage-backup/`
- Create: `C:/Users/18220/.codex/.sage-uninstall.js`

- [ ] **Step 1: 运行 Codex 安装器**

Run: `npx code-abyss --target codex -y`
Expected: 安装器输出完成信息，并生成 `.sage-backup`

- [ ] **Step 2: 校验 Codex 安装结果**

Run: `Get-ChildItem -Force "C:/Users/18220/.codex"`
Expected: 存在新的 `AGENTS.md`、`skills`、`.sage-backup`、`.sage-uninstall.js`

### Task 3: 安装到 Claude Code

**Files:**
- Modify: `C:/Users/18220/.claude/CLAUDE.md`
- Modify: `C:/Users/18220/.claude/output-styles/`
- Modify: `C:/Users/18220/.claude/skills/`
- Modify: `C:/Users/18220/.claude/settings.json`
- Modify: `C:/Users/18220/.claude/ccline/`
- Create: `C:/Users/18220/.claude/.sage-backup/`
- Create: `C:/Users/18220/.claude/.sage-uninstall.js`

- [ ] **Step 1: 运行 Claude 安装器**

Run: `npx code-abyss --target claude -y`
Expected: 安装器输出完成信息，并尝试安装 `ccline`

- [ ] **Step 2: 校验 Claude 安装结果**

Run: `Get-ChildItem -Force "C:/Users/18220/.claude"`
Expected: 存在新的 `CLAUDE.md`、`output-styles`、`skills`、`.sage-backup`、`.sage-uninstall.js`

## Chunk 3: 安装后验证

### Task 4: 验证关键配置是否生效

**Files:**
- Verify: `C:/Users/18220/.codex/AGENTS.md`
- Verify: `C:/Users/18220/.codex/config.toml`
- Verify: `C:/Users/18220/.claude/CLAUDE.md`
- Verify: `C:/Users/18220/.claude/settings.json`

- [ ] **Step 1: 检查 Codex 核心配置**

Run: `Get-Content -Path "C:/Users/18220/.codex/AGENTS.md" -Encoding UTF8 -TotalCount 20`
Expected: 看到 Code Abyss 风格头部内容

- [ ] **Step 2: 检查 Claude 输出风格**

Run: `Get-Content -Path "C:/Users/18220/.claude/settings.json" -Encoding UTF8`
Expected: `outputStyle` 为 `abyss-cultivator`

- [ ] **Step 3: 检查 ccline**

Run: `ccline --version`
Expected: 返回版本号；若失败则记录安装异常

### Task 5: 记录剩余风险

**Files:**
- Verify: `C:/Users/18220/.codex/.sage-backup/manifest.json`
- Verify: `C:/Users/18220/.claude/.sage-backup/`

- [ ] **Step 1: 确认卸载能力仍在**

Run: `Test-Path "C:/Users/18220/.codex/.sage-uninstall.js"; Test-Path "C:/Users/18220/.claude/.sage-uninstall.js"`
Expected: 两条结果都为 `True`

- [ ] **Step 2: 输出回滚命令**

Run: `Write-Output "npx code-abyss --uninstall codex"; Write-Output "npx code-abyss --uninstall claude"`
Expected: 记录完整回滚命令

## 备注

- 本计划不包含 `git commit`，因为用户明确要求不执行提交与分支操作。
