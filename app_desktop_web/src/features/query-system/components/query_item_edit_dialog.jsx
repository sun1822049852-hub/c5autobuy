import { QueryModeAllocationInput } from "./query_mode_allocation_input.jsx";


function formatDialogValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  return `${value}`;
}


function getDialogTitle(context) {
  if (context?.kind === "price") {
    return "修改扫货价";
  }
  if (context?.kind === "wear") {
    return "修改磨损";
  }
  return `修改 ${context?.modeType} 分配`;
}


export function QueryItemEditDialog({
  context,
  item,
  isOpen,
  onAllocationChange,
  onClose,
  onFieldChange,
  remainingByMode,
}) {
  if (!isOpen || !item || !context) {
    return null;
  }

  const dialogTitle = getDialogTitle(context);
  const displayName = item.item_name || item.market_hash_name || item.external_item_id;
  const modeType = context.modeType || null;
  const remainingEntry = modeType ? (remainingByMode[modeType] || {}) : {};

  return (
    <div
      className="surface-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose?.();
        }
      }}
    >
      <section aria-label={dialogTitle} className="dialog-surface query-item-dialog query-item-dialog--single" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">{dialogTitle}</h2>
            <p className="surface-subtitle">{displayName}</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
        </div>

        <div className="form-grid">
          {context.kind === "price" ? (
            <div className="query-item-dialog__single-grid">
              <label className="form-field">
                <span className="form-label">市场价</span>
                <input
                  aria-label="市场价"
                  className="form-input"
                  readOnly
                  type="text"
                  value={formatDialogValue(item.last_market_price)}
                />
              </label>

              <label className="form-field">
                <span className="form-label">扫货价</span>
                <input
                  aria-label="扫货价"
                  className="form-input"
                  min="0"
                  step="0.01"
                  type="number"
                  value={item.max_price ?? ""}
                  onChange={(event) => onFieldChange("maxPrice", event.target.value)}
                />
              </label>
            </div>
          ) : null}

          {context.kind === "wear" ? (
            <>
              <div className="query-item-dialog__natural-card">
                天然磨损范围 {formatDialogValue(item.min_wear)} ~ {formatDialogValue(item.max_wear)}
              </div>

              <div className="query-item-dialog__single-grid">
                <label className="form-field">
                  <span className="form-label">配置最小磨损</span>
                  <input
                    aria-label="配置最小磨损"
                    className="form-input"
                    max="1"
                    min="0"
                    step="0.01"
                    type="number"
                    value={item.detail_min_wear ?? ""}
                    onChange={(event) => onFieldChange("detailMinWear", event.target.value)}
                  />
                </label>

                <label className="form-field">
                  <span className="form-label">配置最大磨损</span>
                  <input
                    aria-label="配置最大磨损"
                    className="form-input"
                    max="1"
                    min="0"
                    step="0.01"
                    type="number"
                    value={item.detail_max_wear ?? ""}
                    onChange={(event) => onFieldChange("detailMaxWear", event.target.value)}
                  />
                </label>
              </div>
            </>
          ) : null}

          {context.kind === "allocation" && modeType ? (
            <div className="query-item-dialog__single-grid">
              <div className="query-item-dialog__natural-card">
                当前状态 {item.statusByMode?.[modeType]?.status_message || "无可用账号"}
              </div>

              <QueryModeAllocationInput
                modeType={modeType}
                overflowCount={remainingEntry.overflowCount ?? 0}
                remainingCount={remainingEntry.remainingCount ?? 0}
                value={item.modeTargets?.[modeType] ?? 0}
                onChange={(value) => onAllocationChange(modeType, value)}
              />
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
