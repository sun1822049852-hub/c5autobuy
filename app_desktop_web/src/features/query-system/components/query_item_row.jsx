const ALL_MODES = ["new_api", "fast_api", "token"];


function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return `${Number(value)}`;
}


function formatWearRange(item) {
  return `${formatValue(item.detail_min_wear)} ~ ${formatValue(item.detail_max_wear)}`;
}


export function QueryItemRow({
  isDeleteMode,
  item,
  onDeleteItem,
  onEditItem,
  onToggleManualPause,
}) {
  const displayName = item.item_name || item.market_hash_name || item.query_item_id;
  const queryItemId = item.query_item_id;

  return (
    <section className="query-item-row" role="region" aria-label={`商品 ${displayName}`}>
      <div className="query-item-row__content">
        <div className="query-item-row__name">{displayName}</div>
        <div className="query-item-row__value query-item-row__value--market-price query-item-row__value--readonly">
          {formatValue(item.last_market_price)}
        </div>
        <button
          className="query-item-row__value query-item-row__value--price"
          type="button"
          aria-label={`修改扫货价 ${displayName}`}
          onClick={() => onEditItem({ queryItemId, kind: "price" })}
        >
          {formatValue(item.max_price)}
        </button>
        <button
          className="query-item-row__value"
          type="button"
          aria-label={`修改磨损 ${displayName}`}
          onClick={() => onEditItem({ queryItemId, kind: "wear" })}
        >
          {formatWearRange(item)}
        </button>
        {ALL_MODES.map((modeType) => (
          <button
            key={modeType}
            className="query-item-row__value query-item-row__value--status"
            type="button"
            aria-label={`修改 ${modeType} ${displayName}`}
            onClick={() => onEditItem({ queryItemId, kind: "allocation", modeType })}
          >
            {item.statusByMode[modeType]?.status_message || "无可用账号"}
          </button>
        ))}
      </div>
      {isDeleteMode ? (
        <button
          className="query-item-row__delete is-visible"
          type="button"
          aria-label={`删除商品 ${displayName}`}
          onClick={() => onDeleteItem(queryItemId)}
        >
          -
        </button>
      ) : (
        <button
          aria-label={`切换手动暂停 ${displayName}`}
          aria-pressed={Boolean(item.manual_paused)}
          className={`query-item-row__control${item.manual_paused ? " is-active" : ""}`}
          type="button"
          onClick={() => onToggleManualPause(queryItemId)}
        >
          手动暂停
        </button>
      )}
    </section>
  );
}
