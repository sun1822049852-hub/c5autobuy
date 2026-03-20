function formatEventMeta(event) {
  const parts = [];

  if (event.query_item_name) {
    parts.push(event.query_item_name);
  }
  if (event.source_mode_type) {
    parts.push(`mode ${event.source_mode_type}`);
  }
  if (Array.isArray(event.product_list) && event.product_list.length) {
    parts.push(`件数 ${event.product_list.length}`);
  }
  if (event.occurred_at) {
    parts.push(event.occurred_at);
  }

  return parts.join(" | ");
}


export function PurchaseRecentEvents({ events }) {
  return (
    <section aria-label="最近事件" className="purchase-recent-events">
      <h2 className="purchase-recent-events__title">最近事件</h2>
      {(events || []).length ? (
        <div className="purchase-recent-events__list">
          {events.map((event, index) => (
            <article
              key={`${event.occurred_at || "event"}-${event.status || "status"}-${index}`}
              className="purchase-recent-events__item"
            >
              <div className="purchase-recent-events__item-top">
                <div className="purchase-recent-events__item-message">{event.message || event.status}</div>
                <div className="purchase-recent-events__item-status">{event.status || "unknown"}</div>
              </div>
              <div className="purchase-recent-events__item-meta">{formatEventMeta(event)}</div>
            </article>
          ))}
        </div>
      ) : (
        <div className="purchase-recent-events__empty">当前还没有最近事件。</div>
      )}
    </section>
  );
}
