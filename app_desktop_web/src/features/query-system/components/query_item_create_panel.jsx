import { QueryModeAllocationInput } from "./query_mode_allocation_input.jsx";


const ALL_MODES = ["new_api", "fast_api", "token"];


export function QueryItemCreatePanel({
  draft,
  isOpen,
  onAdd,
  onAllocationChange,
  onClose,
  onFieldChange,
  onLookup,
  remainingByMode,
}) {
  if (!isOpen) {
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
        aria-label="添加商品"
        className="dialog-surface query-item-dialog"
        role="dialog"
        onSubmit={(event) => {
          event.preventDefault();
          onAdd?.();
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title">添加商品</h2>
            <p className="surface-subtitle">输入 URL 后显式查找商品信息，天然磨损范围只读展示，配置阈值单独保存。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">商品链接</span>
            <input
              className="form-input"
              type="url"
              value={draft.productUrl}
              aria-label="商品链接"
              onChange={(event) => onFieldChange("productUrl", event.target.value)}
            />
          </label>

          <div className="query-item-dialog__lookup-row">
            <button
              className="ghost-button query-item-dialog__lookup-action"
              type="button"
              disabled={draft.isFetching || !String(draft.productUrl || "").trim()}
              onClick={onLookup}
            >
              {draft.isFetching ? "查找中..." : "查找商品信息"}
            </button>
            <div className="query-item-dialog__lookup-hint">使用可用登录账号补全商品信息</div>
          </div>

          {draft.isFetching ? (
            <div className="query-item-dialog__hint">正在拉取商品详情...</div>
          ) : null}
          {draft.fetchError ? (
            <div className="query-item-dialog__error">{draft.fetchError}</div>
          ) : null}

          <div className="query-item-dialog__readonly-grid">
            <label className="form-field">
              <span className="form-label">商品名称</span>
              <input className="form-input" type="text" value={draft.itemName} aria-label="商品名称" readOnly />
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

            <label className="query-item-dialog__checkbox">
              <input
                type="checkbox"
                checked={Boolean(draft.manualPaused)}
                aria-label="手动暂停"
                onChange={(event) => onFieldChange("manualPaused", event.target.checked)}
              />
              <span>手动暂停</span>
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
          <button className="accent-button" type="submit" disabled={draft.isFetching || !draft.itemName}>
            加入当前配置
          </button>
        </div>
      </form>
    </div>
  );
}
