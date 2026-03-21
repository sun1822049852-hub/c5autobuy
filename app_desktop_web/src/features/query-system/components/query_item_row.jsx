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
}) {
  const displayName = item.item_name || item.market_hash_name || item.query_item_id;

  return (
    <section className="query-item-row" role="region" aria-label={`商品 ${displayName}`}>
      <div className="query-item-row__content">
        <div className="query-item-row__name">{displayName}</div>
        <button
          className="query-item-row__value"
          type="button"
          aria-label={`修改价格 ${displayName}`}
          onClick={() => onEditItem(item.query_item_id)}
        >
          {formatValue(item.max_price)}
        </button>
        <button
          className="query-item-row__value"
          type="button"
          aria-label={`修改磨损 ${displayName}`}
          onClick={() => onEditItem(item.query_item_id)}
        >
          {formatWearRange(item)}
        </button>
        {ALL_MODES.map((modeType) => (
          <button
            key={modeType}
            className="query-item-row__value query-item-row__value--status"
            type="button"
            aria-label={`修改 ${modeType} ${displayName}`}
            onClick={() => onEditItem(item.query_item_id)}
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
          onClick={() => onDeleteItem(item.query_item_id)}
        >
          -
        </button>
      ) : null}
    </section>
  );
}
