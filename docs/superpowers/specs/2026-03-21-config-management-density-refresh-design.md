# 配置管理页压缩改造设计

日期：2026-03-21

## 1. 目标

本次改造以 `.superpowers/brainstorm/2026-03-21-config-management-refresh/index.html` 的已确认样例为准，把 `app_desktop_web` 中原本偏“查询工作台”的页面，落成更紧凑的“配置管理”页。

目标只有两类：

1. 收紧布局密度，减少纵向空白。
2. 把配置与商品管理入口压缩到单屏主工作区，不再保留旧 Hero 与底部独立保存条。

## 2. 冻结后的页面结构

页面固定为左右两栏：

1. 左侧窄栏：配置管理列表
2. 右侧主栏：当前配置头部 + 商品配置表

页面内部不再出现：

- `查询系统`
- `查询工作台`
- 旧 Hero 副标题
- 底部独立 `保存区`

侧边主导航中的入口名称统一改为 `配置管理`。

## 3. 左侧配置栏

左栏是紧凑配置管理器，不再使用长按钮和松散卡片。

冻结规则如下：

1. 头部标题为 `配置管理`。
2. 头部右侧只有两个 icon button：绿色 `+`、删除态切换 `-`。
3. `+` 继续复用现有 `新建配置` modal。
4. 顶部 `-` 只负责切换“配置删除态”，不直接执行删除。
5. 默认状态下，每个配置行右侧不显示删除按钮。
6. 进入删除态后，每个配置行右侧浮现小 `-`，点击后进入现有删除确认 modal。
7. 配置行只保留两段主要信息：配置名、当前状态。
8. 当前选中的配置使用高亮边框/底色表现，不再额外堆叠描述信息。

## 4. 当前配置头部

右侧头部压成单个紧凑栏，不再使用大卡片堆叠。

冻结内容如下：

1. 主标题显示当前配置名；未选择时显示 `未选择配置`。
2. 标题右侧紧跟 `当前配置` 标签。
3. 同一行展示三类查询能力容量 chip：`new_api`、`fast_api`、`token`。
4. 同一行展示运行状态与 runtime message，例如 `已停止 / 未运行`、`等待账号 / 等待购买账号恢复`。
5. `保存当前配置` 固定在这一栏右侧。
6. 保存反馈文案保留，但压成头部下方的一小行，不再单独成块。
7. 不再显示配置说明 `description`。

## 5. 商品配置表

商品区不再使用“商品列表”大标题，也不再逐行重复字段标签。

冻结为表头 + 紧凑数据行：

1. 表头与工具按钮同一行。
2. 表头列固定为：
   - `商品名`
   - `价格`
   - `磨损`
   - `new_api`
   - `fast_api`
   - `token`
3. 右上角提供两个 icon button：
   - `+` 添加商品
   - `-` 切换商品删除态
4. 商品行数据必须与表头对齐。
5. 行内只显示值，不再重复“价格/磨损/状态”等小标题。
6. 点击价格、磨损或任一 mode 状态值，直接打开商品编辑 dialog。
7. 删除态关闭时，不显示商品删除按钮。
8. 删除态开启时，每一行右侧浮现小 `-`，允许从当前 draft 中移除商品。

空态文案也按紧凑模式收束：

1. 有配置但无商品时，引导从右上角 `+` 添加商品。
2. 未选中配置时，提示先从左侧选择配置。

## 6. 数据与交互边界

本次只改变配置管理页的布局与已有交互入口，不新增查询业务语义。

允许的行为调整：

1. 新增 `isConfigDeleteMode` / `toggleConfigDeleteMode` 管理左栏删除态。
2. 新增 `isItemDeleteMode` / `toggleItemDeleteMode` 管理商品删除态。
3. 商品删除先从当前 draft 中移除，再在保存时调用后端删除接口持久化。
4. `account_center_client` 需要具备 `deleteQueryItem(configId, queryItemId)`，对应后端：
   - `DELETE /query-configs/{config_id}/items/{query_item_id}`

明确不在本次范围：

1. 查询调度算法调整
2. 商品解析流程重写
3. 购买系统 UI 改版
4. 新增运行控制按钮

## 7. 落地文件

真实实现应主要落在以下文件：

- `app_desktop_web/src/features/shell/app_shell.jsx`
- `app_desktop_web/src/features/purchase-system/components/purchase_config_selector_dialog.jsx`
- `app_desktop_web/src/api/account_center_client.js`
- `app_desktop_web/src/features/query-system/query_system_page.jsx`
- `app_desktop_web/src/features/query-system/hooks/use_query_system_page.js`
- `app_desktop_web/src/features/query-system/components/query_config_nav.jsx`
- `app_desktop_web/src/features/query-system/components/query_workbench_header.jsx`
- `app_desktop_web/src/features/query-system/components/query_item_table.jsx`
- `app_desktop_web/src/features/query-system/components/query_item_row.jsx`
- `app_desktop_web/src/styles/app.css`

## 8. 验收口径

完成后应满足：

1. 页面与导航中统一使用 `配置管理`。
2. 页面中不再出现 `查询工作台` Hero。
3. 左栏头部为 `+ / -` 紧凑按钮。
4. 配置删除按钮仅在配置删除态中出现。
5. 当前配置头部只保留一条紧凑主信息行 + 一条保存反馈行。
6. 页面底部不再存在独立保存条。
7. 商品区表头与 `+ / -` 工具栏同排显示。
8. 商品行数值与表头列对齐。
9. 点击商品数值可进入编辑。
10. 商品删除按钮仅在商品删除态中出现。
