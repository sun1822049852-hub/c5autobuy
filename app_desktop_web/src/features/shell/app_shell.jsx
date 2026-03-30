import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";

const NAV_ITEMS = [
  {
    id: "account-center",
    label: "账号中心",
    tag: "Live",
  },
  {
    id: "query-system",
    label: "配置管理",
    tag: "Live",
  },
  {
    id: "purchase-system",
    label: "扫货系统",
    tag: "Live",
  },
  {
    id: "query-stats",
    label: "查询统计",
    tag: "Live",
  },
  {
    id: "account-capability-stats",
    label: "账号能力统计",
    tag: "Live",
  },
  {
    id: "diagnostics",
    label: "通用诊断",
    tag: "Live",
  },
];


export function AppShell({ activeItem, children, onSelect, reloadNotice = null }) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar" aria-label="主导航">
        <div className="app-shell__brand" style={NO_SELECT_STYLE}>
          <div className="app-shell__brand-mark">Desktop Web</div>
          <div className="app-shell__brand-title">C5 控制台</div>
          <div className="app-shell__brand-copy">
            新桌面壳复用现有 Python 后端，逐步接管旧 UI。
          </div>
        </div>
        <nav className="app-shell__nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              aria-label={item.label}
              className={`app-shell__nav-button${item.id === activeItem ? " is-active" : ""}${item.disabled ? " is-disabled" : ""}`}
              disabled={item.disabled}
              style={NO_SELECT_STYLE}
              type="button"
              onClick={() => {
                if (!item.disabled) {
                  onSelect?.(item.id);
                }
              }}
            >
              <span className="app-shell__nav-button-label">{item.label}</span>
              <span aria-hidden="true" className="app-shell__nav-button-tag">{item.tag}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="app-shell__content">
        {reloadNotice ? (
          <section className="app-shell__reload-notice" role="status">
            <span className="app-shell__reload-notice-title">Renderer Reload</span>
            <span className="app-shell__reload-notice-text">
              检测到界面已重新加载，已尝试恢复到「{reloadNotice.activeItemLabel}」视图。
            </span>
          </section>
        ) : null}
        {children}
      </main>
    </div>
  );
}
