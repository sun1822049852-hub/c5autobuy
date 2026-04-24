# 桌面安装包体积极限优化路径

> 日期: 2026-04-24 | 状态: 实施中

## 背景

桌面端 Electron 安装包（NSIS）从 283 MB 膨胀到不可接受的体积。根因是开发环境 `.venv`（721 MB）曾被整包打入 release，其中 PySide6 独占 628 MB（UI 已是 Electron + React，完全不需要 Qt）。

commit `580670a` 已完成第一刀：用 `build/python_deps`（精简 site-packages）替代 `.venv`，并实现用户侧自动下载 Python embeddable runtime 的 bootstrap 机制。

本文档记录在此基础上的进一步极限瘦身路径。

## 体积分解（优化前 win-unpacked 1.1 GB）

| 组件 | 大小 | 占比 |
|------|------|------|
| resources/.venv（已移除） | 721 MB | 66% |
| Electron 核心 (exe+dll+pak) | 275 MB | 25% |
| locales（55 个语言包） | 43 MB | 4% |
| app.asar（含历史构建产物） | 22 MB | 2% |
| 其余 | ~39 MB | 3% |

## 优化措施清单

### P0 — 已完成（580670a）

| 措施 | 节省 | 文件 |
|------|------|------|
| `.venv` → `build/python_deps` + 用户侧 bootstrap | ~631 MB | `electron-builder.config.cjs`, `python_runtime_bootstrap.js` |

### P1 — 排除列表扩充（本轮实施）

| 措施 | 节省 | 文件 |
|------|------|------|
| selenium + 依赖链（trio/wsproto/outcome/sortedcontainers/PySocks）加入排除 | ~25 MB | `python_runtime_config.cjs` |
| pkg_resources、pytest_asyncio、pytestqt、py_spy 加入排除 | ~3 MB | `python_runtime_config.cjs` |

验证方法：`app_backend/` 源码中无 `import selenium`、`import trio`、`import pkg_resources`。

### P2 — 过滤增强（本轮实施）

| 措施 | 节省 | 文件 |
|------|------|------|
| `buildCopyFilter` 增加 `.dist-info/` 排除 | ~3-5 MB | `python_runtime_resources.cjs` |
| `buildCopyFilter` 增加依赖内 `tests/` 目录排除 | ~2 MB | `python_runtime_resources.cjs` |
| `buildCopyFilter` 增加 `__editable__` / `.pth` 排除 | ~100 KB | `python_runtime_resources.cjs` |
| `__pycache__` 匹配修复（目录本身 + 子路径） | ~8 MB | `python_runtime_resources.cjs` |
| electron-builder filter 增加 `.dist-info`、`tests/`、`test_*` | 双重保险 | `electron-builder.config.cjs` |

### P3 — 构建配置优化（本轮实施）

| 措施 | 节省 | 文件 |
|------|------|------|
| `compression: "maximum"` | 安装包再缩 20-30% | `electron-builder.config.cjs` |
| `electronLanguages: ["zh-CN", "en-US"]` | ~41 MB (unpacked) | `electron-builder.config.cjs` |
| `build.emptyOutDir: true` | ~18 MB (清除 dist/ 历史产物) | `vite.config.js` |

### P4 — 未来可选（未实施）

| 措施 | 预估节省 | 风险 | 说明 |
|------|----------|------|------|
| 移除 Chromium GPU DLL (dxcompiler/vk_swiftshader) | ~32 MB | 高 — 特定硬件兼容性 | 需 afterPack hook |
| UPX 压缩 Electron 二进制 | ~80 MB | 高 — 可能触发杀软误报 | 不推荐 |
| pytz 移除（后端只用 datetime.timezone） | ~2 MB | 低 — 需确认无运行时引用 | pyproject.toml 声明了但源码未 import |

## 预估效果

| 阶段 | win-unpacked | NSIS 安装包 |
|------|-------------|-------------|
| 旧方案（含 .venv） | 1.1 GB | 283 MB |
| P0 完成后 | ~380 MB | ~130 MB |
| P0 + P1 + P2 + P3 | ~290 MB | ~70-80 MB |

## 关键文件索引

| 文件 | 职责 |
|------|------|
| `app_desktop_web/python_runtime_config.cjs` | 排除列表 + embeddable Python 版本配置 |
| `app_desktop_web/python_runtime_resources.cjs` | preflight: 从 .venv 提取精简 python_deps |
| `app_desktop_web/python_runtime_bootstrap.js` | 运行时: 用户侧下载 + 校验 + 解压 + patch |
| `app_desktop_web/electron-builder.config.cjs` | electron-builder 打包配置 |
| `app_desktop_web/electron-builder-preflight.cjs` | 打包前置脚本入口 |
| `app_desktop_web/vite.config.js` | 前端构建配置 |

## 验证步骤

1. 清理旧产物: `rm -rf app_desktop_web/release/`
2. 重建前端: `npm --prefix app_desktop_web run build`（会自动清理 dist/）
3. 打包: `npm --prefix app_desktop_web run pack:win`
4. 检查 `release/win-unpacked/` 体积
5. 确认 `resources/` 下无 `.venv` 目录
6. 确认 `resources/python_deps/Lib/site-packages/` 下无 PySide6、selenium 等排除包
7. 确认 locales 只有 zh-CN.pak 和 en-US.pak
8. 检查 NSIS 安装包大小

## 注意事项

- `compression: "maximum"` 会显著增加打包时间（从 ~2 分钟到 ~5-8 分钟），但安装包体积收益明显
- `electronLanguages` 裁剪不影响应用内中文显示，只影响 Chromium 内置的 locale 资源
- `.dist-info` 排除不影响运行时（Python 只在 pip 操作时读取 dist-info）
- `__editable__` / `.pth` 排除是必要的：editable install 的路径在打包后无效，留着反而可能干扰 sys.path
