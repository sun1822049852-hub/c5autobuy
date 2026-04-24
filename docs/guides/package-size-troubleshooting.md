# 桌面打包体积排障与优化指南

> 最后验证: 2026-04-24 | 验证结果: win-unpacked 从 1.1 GB 降至 296 MB

## 快速定位：体积又膨胀了？

按以下顺序排查，命中即止。

### 1. `.venv` 是否又被打入了？

```bash
ls release/win-unpacked/resources/.venv
```

如果存在 → `.venv` 被重新打入了。检查 `electron-builder.config.cjs` 的 `extraResources`，确认没有 `.venv` 条目。当前正确配置只打入 `build/python_deps`。

根因回顾：历史上 `.venv`（721 MB，含 PySide6 628 MB）曾通过 `extraResources` 整包打入。commit `580670a` 已切换到精简的 `python_deps` + 用户侧 bootstrap。

### 2. `python_deps` 里是否混入了不该有的大包？

```bash
du -sh release/win-unpacked/resources/python_deps/Lib/site-packages/*/ | sort -rh | head -15
```

正常值约 37 MB。如果远超此值，检查以下包是否泄漏：

| 包 | 正常状态 | 大小 | 排除位置 |
|----|----------|------|----------|
| PySide6 | 不应存在 | 628 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| shiboken6 | 不应存在 | 3 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| selenium | 不应存在 | 22 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| trio | 不应存在 | 2 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| pip | 不应存在 | 6 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| setuptools | 不应存在 | 3.4 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| pytest/_pytest | 不应存在 | 1.4 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |
| pygments | 不应存在 | 5 MB | `EXCLUDED_TOP_LEVEL_ENTRIES` |

修复方法：在 `app_desktop_web/python_runtime_config.cjs` 的 `EXCLUDED_TOP_LEVEL_ENTRIES` 数组中添加包名，然后清理缓存重建：

```bash
rm -rf app_desktop_web/build/python_deps app_desktop_web/release
npm --prefix app_desktop_web run pack:win
```

**关键陷阱**：`build/python_deps` 是缓存目录。修改排除列表后必须删除它，否则 preflight 会复用旧缓存，新排除项不生效。

### 3. `app.asar` 是否异常膨胀？

```bash
du -sh release/win-unpacked/resources/app.asar
```

正常值约 7-8 MB。如果远超（如 22 MB），说明 `dist/` 目录累积了历史构建产物。

修复方法：

```bash
rm -rf app_desktop_web/dist
npm --prefix app_desktop_web run build   # vite build 会自动清理（emptyOutDir: true）
```

`vite.config.js` 中的 `build.emptyOutDir: true` 保证每次 vite build 清理 dist/，但如果 preflight 的 `ensureRendererBuild` 判断 dist 比源码新而跳过构建，旧文件就会残留。

### 4. locales 是否全量打入？

```bash
ls release/win-unpacked/locales/
```

正常只有 `en-US.pak` 和 `zh-CN.pak`（共 ~1 MB）。如果有 55 个 `.pak` 文件（~43 MB），检查 `electron-builder.config.cjs` 中是否有：

```javascript
electronLanguages: ["zh-CN", "en-US"],
```

### 5. 打包时 electron-builder 下载超时？

```
⨯ Get "https://github.com/electron/electron/releases/download/v37.2.0/...": read tcp ... wsarecv: ...
```

这是 GitHub 网络不通。解决方案：在 `electron-builder.config.cjs` 中加入 `electronDist` 指向本地已有的 electron 二进制：

```javascript
electronDist: path.join(normalizedAppDir, "node_modules", "electron", "dist"),
```

前提是 `node_modules/electron/dist/` 下有完整的 electron 二进制（`electron.exe` 等）。

---

## 架构全景

```
打包流程:
  npm run pack:win
    ├── prepack:win → electron-builder-preflight.cjs
    │   ├── ensureRendererBuild()     → vite build → dist/
    │   ├── preparePackagedPythonResources() → build/python_deps/
    │   │   ├── 源: .venv/Lib/site-packages/
    │   │   ├── 排除: EXCLUDED_TOP_LEVEL_ENTRIES (python_runtime_config.cjs)
    │   │   └── 过滤: buildCopyFilter (python_runtime_resources.cjs)
    │   └── verifyPackagedPythonResources() → import 验证
    └── electron-builder --dir
        ├── files → dist/ + 主进程文件 → app.asar
        ├── extraResources → app_backend/ + python_deps/ + xsign.py
        ├── electronDist → node_modules/electron/dist/ (跳过下载)
        ├── electronLanguages → zh-CN + en-US
        └── compression: "maximum"

用户侧首次启动:
  electron-main.cjs → ensureManagedPythonRuntime()
    ├── 下载 python-3.11.9-embeddable-amd64.zip (~15 MB)
    ├── SHA256 校验
    ├── 解压到 userData/app-private/python-runtime/3.11.9/
    ├── 从 resources/python_deps 复制 site-packages
    ├── patch python311._pth
    └── 写入 manifest → 后续启动直接复用
```

## 关键文件速查

| 文件 | 改什么 | 什么时候改 |
|------|--------|-----------|
| `python_runtime_config.cjs` | `EXCLUDED_TOP_LEVEL_ENTRIES` 排除列表 | 新增/移除 Python 依赖时 |
| `python_runtime_resources.cjs` | `buildCopyFilter` 过滤规则 | 需要排除新类型文件时 |
| `electron-builder.config.cjs` | 打包配置（compression/locales/filter/electronDist） | 打包行为调整时 |
| `electron-builder-preflight.cjs` | preflight 流程入口 | 一般不需要改 |
| `python_runtime_bootstrap.js` | 用户侧 Python runtime 下载逻辑 | Python 版本升级时 |
| `vite.config.js` | `build.emptyOutDir` | 一般不需要改 |

## 排除列表当前完整清单

`python_runtime_config.cjs` → `EXCLUDED_TOP_LEVEL_ENTRIES`（21 项）：

```
GUI:        PySide6, shiboken6
浏览器自动化: selenium, trio, trio_websocket, wsproto, outcome, sortedcontainers, PySocks
包管理:      pip, setuptools, wheel, pkg_resources
测试:        pytest, _pytest, pytest_asyncio, pytestqt, py_spy, pluggy, iniconfig
Dev工具:     pygments
```

`buildCopyFilter` 额外排除：
- `__pycache__/` 目录及内容
- `.pytest_cache/` 目录及内容
- `*.pyc` 文件
- `.dist-info/` 元数据目录
- 依赖内的 `tests/` / `test/` 目录（不影响 app_backend）
- `__editable__` 和 `.pth` 文件（editable install 残留）

## 过滤层级（双重保险）

体积过滤分两层，任一层命中即排除：

| 层级 | 位置 | 作用时机 |
|------|------|----------|
| 第一层: preflight | `EXCLUDED_TOP_LEVEL_ENTRIES` + `buildCopyFilter` | `.venv` → `build/python_deps` 复制时 |
| 第二层: electron-builder | `extraResources[].filter` glob | `build/python_deps` → `release/` 打包时 |

## 验证基准（2026-04-24）

| 组件 | 基准值 | 异常阈值 |
|------|--------|----------|
| win-unpacked 总计 | 296 MB | > 350 MB 需排查 |
| resources/ | 47 MB | > 60 MB 需排查 |
| python_deps/ | 37 MB | > 50 MB 需排查 |
| app.asar | 7.8 MB | > 15 MB 需排查 |
| locales/ | 1 MB | > 5 MB 需排查 |

## 新增 Python 依赖时的检查清单

1. 确认 `app_backend/` 源码中确实有 `import xxx`
2. 检查该依赖的体积：`du -sh .venv/Lib/site-packages/xxx/`
3. 如果 > 5 MB，评估是否有更轻量的替代
4. 如果是纯开发/测试依赖，加入 `EXCLUDED_TOP_LEVEL_ENTRIES`
5. 打包后验证：`du -sh release/win-unpacked/resources/python_deps/`
