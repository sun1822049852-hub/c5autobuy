const TAB_ITEMS = [
  { id: "query", label: "查询" },
  { id: "purchase", label: "购买" },
  { id: "login_tasks", label: "登录任务" },
];


export function DiagnosticsTabs({ activeTab, onSelect }) {
  return (
    <div className="diagnostics-tabs" role="tablist" aria-label="诊断标签">
      {TAB_ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === activeTab}
          className={`diagnostics-tabs__button${item.id === activeTab ? " is-active" : ""}`}
          onClick={() => onSelect?.(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
