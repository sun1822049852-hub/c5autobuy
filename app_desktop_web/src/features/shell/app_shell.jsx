const NAV_ITEMS = [
  {
    id: "account-center",
    label: "账号中心",
    tag: "Live",
  },
  {
    id: "query-system",
    label: "查询系统（即将迁移）",
    tag: "Soon",
  },
  {
    id: "purchase-system",
    label: "购买系统（即将迁移）",
    tag: "Soon",
  },
];


export function AppShell({ activeItem, children }) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar" aria-label="主导航">
        <div className="app-shell__brand">
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
              className={`app-shell__nav-button${item.id === activeItem ? " is-active" : ""}`}
              type="button"
            >
              <span className="app-shell__nav-button-label">{item.label}</span>
              <span aria-hidden="true" className="app-shell__nav-button-tag">{item.tag}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="app-shell__content">{children}</main>
    </div>
  );
}
