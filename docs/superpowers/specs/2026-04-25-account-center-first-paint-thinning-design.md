# Account Center First Paint Thinning Design

> 日期: 2026-04-25 | 状态: 已确认，待执行

## 背景

`startup thinning` 主线已经把首屏等待从 backend heavy slice 挪走，并证明当前桌面首页慢点不再落在 backend startup。

最新有效真机样本（`C5_STARTUP_TRACE=1` + `C5_LOCAL_DEBUG_REUSE_RENDERER_DIST=1`）显示：

- `desktop.window.visible` `751ms`
- `desktop.backend.ready` `3615ms`
- `renderer.bootstrap.config.consumed` `3618ms`
- `renderer.account.center.chunk.ready` `3626ms`
- `renderer.account.center.first.commit` `6387ms`
- `renderer.account.center.accounts.loaded` `6421ms`

这说明：

- `backend.ready -> account-center chunk.ready` 已只剩约 `11ms`
- `account-center first.commit -> accounts.loaded` 已只剩约 `34ms`
- 当前主慢点是 `account-center chunk.ready -> first.commit`，约 `2.76s`

换句话说，首页当前慢的不是 backend，也不是账号列表接口，而是账号中心页面模块在“真正挂上首屏”前的同步渲染闭包仍然过大。

## 用户目标

魔尊已明确选择：

- 优先“更快可见可点”
- 可以接受 `代理管理 / 购买配置 / 日志 / 登录抽屉` 这类非首屏必须面板在第一次点开时再慢半拍加载

## 目标

把账号中心首页继续压成“最小可操作闭包”，让桌面 backend ready 后尽快进入：

- 可见：侧栏、首页主框架、账号列表区、搜索、刷新、添加账号
- 可点：上述首屏主操作立即可点
- 可后置：非首屏必须的对话框、抽屉、上下文菜单、日志、代理池等面板第一次打开时再加载

## 非目标

- 不回头修改 backend startup slice
- 不取消现有 shell-only、`/health ready=true`、browser-actions lazy 边界
- 不改登录成功链、open-api 链、`query -> hit -> purchase` 主链
- 不把“首屏快了”伪装成“整个账号中心所有交互都同时 ready”

## 方案对比

### 方案 A：账号中心首屏最小闭包 + 非首屏面板按首次交互 lazy 加载

做法：

- `AccountCenterPage` 首屏只保留 hero / toolbar / table / 最小列表查询
- 把 `ProxyPoolDialog`、`PurchaseConfigDrawer`、`LoginDrawer`、日志面板、右键菜单、各类编辑对话框移出首屏同步闭包
- 这些面板第一次被点开时再 `import()` 和挂载

优点：

- 直接命中当前 `chunk.ready -> first.commit` 的真慢点
- 不需要改 backend，不碰 `/account-center/accounts`
- 对“更快可见可点”最贴合

缺点：

- 第一次点开重面板会有一次 lazy 成本
- 需要梳理账号中心当前把大量 overlay 都同步挂在页面底部的结构

### 方案 B：取消 account-center 首屏 `React.lazy`

做法：

- 直接把 `AccountCenterPage` 改回首页同步 import，避免首页进入时再走 chunk 解析

优点：

- 改动表面上最少

缺点：

- 当前证据已经表明 `backend.ready -> chunk.ready` 只剩约 `11ms`
- 真慢点不在 chunk 下载/解析，因此收益非常有限
- 还会把首页 bundle 再做大

### 方案 C：预热 account-center chunk，但保留页面内部同步大闭包

做法：

- 在 backend ready 前后主动预热 `AccountCenterPage` chunk

优点：

- 可以进一步压缩 chunk ready 的尾巴

缺点：

- 只能继续优化已经很短的 `~11ms`
- 无法解决 `first.commit` 之前仍然存在的 `~2.76s` 同步渲染开销

## 结论

采用 **方案 A**。

理由很简单：当前已经不是“页面代码何时下载到”慢，而是“页面拿到代码后首帧同步要做的事太多”。继续去碰 chunk 预热，只会砍掉一段已经不值钱的时间。

## 设计

### 1. 首屏必须保留的闭包

账号中心首页首帧只允许同步保留：

- `OverviewCards`
- `AccountTable`
- 搜索 / 刷新 / 添加账号 / 代理管理按钮本身
- 账号列表最小查询与筛选状态
- 首屏必要的只读提示

这些内容的目标不是“所有能力都 ready”，而是“人已经能看见主界面、定位账号、开始交互”。

### 2. 延后到首次交互的面板

以下面板默认从首帧同步闭包中移出：

- `ProxyPoolDialog`
- `PurchaseConfigDrawer`
- `LoginDrawer`
- `AccountLogsModal`
- `AccountContextMenu`
- `AccountCreateDialog`
- `AccountDeleteDialog`
- `AccountRemarkDialog`
- `AccountApiKeyDialog`
- `AccountBrowserProxyDialog`
- `AccountProxyDialog`
- `FeatureUnavailableDialog`

口径：

- 按钮、入口、占位可以先出现
- 真正的面板组件第一次被点击时才加载
- 第一次点击期间允许出现局部 loading / skeleton，不允许把首页主框架重新打黑或整页阻塞

### 3. 状态拆分原则

账号中心当前把大量 overlay 状态和动作都提前绑定在同一个页面闭包里。后续执行时要按两层拆：

- 首屏层：
  - 列表查询
  - hero / toolbar / search / filter
  - 最小按钮事件入口
- 交互层：
  - 各类 dialog/drawer/modal/context-menu 的 open state
  - 这些面板专属的副作用和数据请求

核心原则：

- 首屏只保留“点按钮能触发后续加载”的入口
- 不让某个 rarely-used overlay 的初始化，反向拖慢整页 first commit

### 4. 体验约束

- 首屏默认页仍固定为 `account-center`
- 首屏仍必须在 backend ready 后立即接主进程 bootstrap 更新
- `刷新`、`搜索`、`添加账号` 这些首屏主动作不能因为 overlay lazy 化而失效
- 第一次打开延后面板时，允许局部等待，但不能遮掉整个首页

## 文件范围

优先涉及：

- `app_desktop_web/src/App.jsx`
- `app_desktop_web/src/features/account-center/account_center_page.jsx`
- `app_desktop_web/src/features/account-center/hooks/use_account_center_page.js`
- `app_desktop_web/src/features/proxy-pool/use_proxy_pool.js`
- `app_desktop_web/tests/renderer/account_center_page.test.jsx`
- `app_desktop_web/tests/renderer/app_remote_bootstrap.test.jsx`
- `docs/agent/session-log.md`

如执行中发现 `account_center_page.jsx` 继续膨胀，可新增专门的 overlay lazy 容器文件，但不做无关重构。

## 验证标准

### 自动化

- 账号中心 renderer focused tests 通过
- desktop bootstrap 相关 renderer / electron tests 继续通过

### 真机 trace

至少复测：

- `desktop.window.visible`
- `desktop.backend.ready`
- `renderer.bootstrap.config.consumed`
- `renderer.account.center.chunk.ready`
- `renderer.account.center.first.commit`
- `renderer.account.center.accounts.loaded`

期望：

- `backend.ready -> chunk.ready` 保持当前低值，不回退
- `chunk.ready -> first.commit` 继续明显下降

## 风险与回退

### 风险

- 过度 lazy 化可能把“首屏可点”变成“点了还得等多个 overlay 连锁加载”
- 若某些首屏按钮实际上隐式依赖 drawer/dialog 初始化，拆分时容易误伤

### 回退原则

- 若首屏按钮出现可见但不可用，先回退对应 overlay 的 lazy 化，不动当前已经生效的 storage 热路径修正
- 若真机 trace 显示 first commit 没继续下降，说明这批 overlay 不是主要热源，下一轮改查 `AccountTable` / hero / hook 本身，而不是继续盲拆 backend 或 chunk preload
