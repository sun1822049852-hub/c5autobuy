export function ErrorNotice({ className = "query-system-page__error", details = [], message }) {
  if (!message) {
    return null;
  }

  return (
    <section className={className} role="alert">
      <div className="query-system-page__error-message">{message}</div>
      {details.length ? (
        <div className="query-system-page__error-details">
          {details.map((line, index) => (
            <div key={`${line}-${index}`} className="query-system-page__error-detail">
              {line}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
