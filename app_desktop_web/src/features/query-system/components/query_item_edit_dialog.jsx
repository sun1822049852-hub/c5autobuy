import { QueryModeAllocationInput } from "./query_mode_allocation_input.jsx";


const ALL_MODES = ["new_api", "fast_api", "token"];


export function QueryItemEditDialog({
  draft,
  isOpen,
  onAllocationChange,
  onApply,
  onClose,
  onFieldChange,
  remainingByMode,
}) {
  if (!isOpen || !draft) {
    return null;
  }

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
      <form
        aria-label="编辑商品"
        className="dialog-surface query-item-dialog"
        role="dialog"
        onSubmit={(event) => {
          event.preventDefault();
          onApply?.();
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title">编辑商品</h2>
            <p className="surface-subtitle">{draft.itemName || draft.marketHashName || draft.externalItemId}</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
        </div>

        <div className="form-grid">
          <div className="query-item-dialog__readonly-grid">
            <label className="form-field">
              <span className="form-label">商品链接</span>
              <input className="form-input" type="text" value={draft.productUrl} aria-label="商品链接" readOnly />
            </label>

            <label className="form-field">
              <span className="form-label">外部商品 ID</span>
              <input className="form-input" type="text" value={draft.externalItemId} aria-label="外部商品 ID" readOnly />
            </label>
          </div>

          <div className="query-item-dialog__natural-card">
            天然磨损范围 {draft.minWear === "" ? "--" : draft.minWear} ~ {draft.maxWear === "" ? "--" : draft.maxWear}
          </div>

          <div className="query-item-dialog__field-grid">
            <label className="form-field">
              <span className="form-label">配置最小磨损</span>
              <input
                className="form-input"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={draft.detailMinWear}
                aria-label="配置最小磨损"
                onChange={(event) => onFieldChange("detailMinWear", event.target.value)}
              />
            </label>

            <label className="form-field">
              <span className="form-label">配置最大磨损</span>
              <input
                className="form-input"
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={draft.detailMaxWear}
                aria-label="配置最大磨损"
                onChange={(event) => onFieldChange("detailMaxWear", event.target.value)}
              />
            </label>

            <label className="form-field">
              <span className="form-label">扫货价</span>
              <input
                className="form-input"
                type="number"
                min="0"
                step="0.01"
                value={draft.maxPrice}
                aria-label="扫货价"
                onChange={(event) => onFieldChange("maxPrice", event.target.value)}
              />
            </label>

            <label className="form-field">
              <span className="form-label">暂停状态</span>
              <span className="query-item-dialog__checkbox">
                <input
                  type="checkbox"
                  checked={Boolean(draft.manualPaused)}
                  aria-label="手动暂停"
                  onChange={(event) => onFieldChange("manualPaused", event.target.checked)}
                />
                <span>手动暂停</span>
              </span>
            </label>
          </div>

          <div className="query-item-dialog__allocation-grid">
            {ALL_MODES.map((modeType) => (
              <QueryModeAllocationInput
                key={modeType}
                modeType={modeType}
                value={draft.modeAllocations[modeType] ?? 0}
                remainingCount={remainingByMode[modeType]?.remainingCount ?? 0}
                overflowCount={remainingByMode[modeType]?.overflowCount ?? 0}
                onChange={(value) => onAllocationChange(modeType, value)}
              />
            ))}
          </div>
        </div>

        <div className="surface-actions">
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
          <button className="accent-button" type="submit">应用修改</button>
        </div>
      </form>
    </div>
  );
}
