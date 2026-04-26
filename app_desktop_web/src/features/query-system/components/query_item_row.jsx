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
  readOnly = false,
  onDeleteItem,
  onEditItem,
  onToggleManualPause,
}) {
  const displayName = item.item_name || item.market_hash_name || item.query_item_id;
  const queryItemId = item.query_item_id;
  const isPaused = Boolean(item.manual_paused);

  return (
    <section className="query-item-row" role="region" aria-label={`商品 ${displayName}`}>
      <div className="query-item-row__content query-item-table__grid-track">
        <div className="query-item-row__name">{displayName}</div>
        <div className="query-item-row__value query-item-row__value--market-price query-item-row__value--readonly">
          {formatValue(item.last_market_price)}
        </div>
        <button
          className="query-item-row__value query-item-row__value--price"
          type="button"
          aria-label={`修改扫货价 ${displayName}`}
          disabled={readOnly}
          onClick={() => onEditItem({ queryItemId, kind: "price" })}
        >
          {formatValue(item.max_price)}
        </button>
        <button
          className="query-item-row__value"
          type="button"
          aria-label={`修改磨损 ${displayName}`}
          disabled={readOnly}
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
            disabled={readOnly}
            onClick={() => onEditItem({ queryItemId, kind: "allocation", modeType })}
          >
            {item.statusByMode[modeType]?.status_message || "无可用账号"}
          </button>
        ))}
        {isDeleteMode ? (
          <button
            className="query-item-row__delete is-visible"
            type="button"
            aria-label={`删除商品 ${displayName}`}
            disabled={readOnly}
            onClick={() => onDeleteItem(queryItemId)}
          >
            -
          </button>
        ) : (
          <button
            aria-label={`切换手动暂停 ${displayName}`}
            aria-pressed={isPaused}
            className={`query-item-row__status-toggle${isPaused ? " is-paused" : " is-running"}`}
            type="button"
            disabled={readOnly}
            onClick={() => onToggleManualPause(queryItemId)}
          >
            <span className="query-item-row__status-icon" aria-hidden="true" />
            <span className="query-item-row__status-label" aria-hidden="true">
              {isPaused ? "已暂停" : "运行中"}
            </span>
          </button>
        )}
      </div>
      <div aria-hidden="true" className="query-item-row__toolbar-spacer" />
    </section>
  );
}
