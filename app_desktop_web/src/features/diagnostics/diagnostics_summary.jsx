export function DiagnosticsSummary({ items = [] }) {
  return (
    <section className="diagnostics-summary" aria-label="诊断摘要">
      {items.map((item) => (
        <article
          key={item.label}
          className={`diagnostics-summary__card${item.tone ? ` is-${item.tone}` : ""}`}
        >
          <div className="diagnostics-summary__label">{item.label}</div>
          <div className="diagnostics-summary__value">{item.value}</div>
          {item.hint ? (
            <div className="diagnostics-summary__hint">{item.hint}</div>
          ) : null}
        </article>
      ))}
    </section>
  );
}
