const ALL_MODES = ["new_api", "fast_api", "token"];


function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return `${Number(value)}`;
}


export function QueryItemRow({
  item,
  onEditItem,
}) {
  const displayName = item.item_name || item.market_hash_name || item.query_item_id;

  return (
    <section className="query-item-row" role="region" aria-label={`商品 ${displayName}`}>
      <div className="query-item-row__summary">
        <div className="query-item-row__headline">
          <h3 className="query-item-row__title">{displayName}</h3>
          <button
            className="ghost-button query-item-row__action"
            type="button"
            onClick={() => onEditItem(item.query_item_id)}
          >
            {`编辑 ${displayName}`}
          </button>
        </div>

        <div className="query-item-row__metrics">
          <span className="query-item-row__metric">价格 {formatValue(item.max_price)}</span>
          <span className="query-item-row__metric">
            磨损 {formatValue(item.detail_min_wear)} ~ {formatValue(item.detail_max_wear)}
          </span>
          {ALL_MODES.map((modeType) => (
            <span key={modeType} className="query-item-row__metric">
              {modeType} {item.modeTargets[modeType] ?? 0}
            </span>
          ))}
        </div>

        <div className="query-item-row__statuses">
          {ALL_MODES.map((modeType) => (
            <span key={modeType} className="query-item-row__status-chip">
              {modeType}：{item.statusByMode[modeType]?.status_message || "无可用账号"}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
