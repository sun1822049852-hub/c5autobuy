export function RuntimePageGuard({ description, error = "", onRetry = null, title }) {
  return (
    <section className="app-shell__startup-panel" role="status" aria-live="polite">
      <span className="app-shell__startup-panel-eyebrow">Runtime Bootstrap</span>
      <h2 className="app-shell__startup-panel-title">{title}</h2>
      <p className="app-shell__startup-panel-text">{description}</p>
      {error ? <p className="app-shell__startup-panel-text">{error}</p> : null}
      {error && typeof onRetry === "function" ? (
        <button className="ghost-button" type="button" onClick={onRetry}>
          重试加载运行时
        </button>
      ) : null}
    </section>
  );
}
