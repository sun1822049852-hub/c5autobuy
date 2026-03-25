export function DiagnosticsEventList({
  emptyText = "暂无事件",
  rows = [],
  timeKey = "timestamp",
  title = "最近事件",
}) {
  return (
    <section className="diagnostics-section" aria-label={title}>
      <header className="diagnostics-section__header">
        <h3 className="diagnostics-section__title">{title}</h3>
      </header>
      {rows.length ? (
        <div className="diagnostics-event-list">
          {rows.map((row, index) => (
            <article key={`${row[timeKey] ?? "event"}-${index}`} className="diagnostics-event-list__item">
              <div className="diagnostics-event-list__top">
                <span className="diagnostics-event-list__time">{row[timeKey]}</span>
                <span className="diagnostics-event-list__status">
                  {row.level || row.status || row.state || "event"}
                </span>
              </div>
              <div className="diagnostics-event-list__message">{row.message || row.last_message || "无详情"}</div>
              <div className="diagnostics-event-list__meta">
                {[
                  row.account_display_name,
                  row.query_item_name,
                  row.mode_type || row.source_mode_type,
                  row.error,
                ].filter(Boolean).join(" · ")}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="diagnostics-empty">{emptyText}</div>
      )}
    </section>
  );
}
