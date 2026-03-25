const MODE_LABELS = {
  new_api: "api查询器",
  fast_api: "api高速查询器",
  token: "浏览器查询器",
};


export function getPurchaseModeLabel(modeType) {
  return MODE_LABELS[modeType] || modeType || "未知查询器";
}


export function PurchaseModeAllocationInput({
  actualCount = 0,
  canDecrease = false,
  canIncrease = false,
  disabled = false,
  modeType,
  sharedAvailableCount = 0,
  statusMessage = "未运行",
  targetCount = 0,
  onDecrease,
  onIncrease,
}) {
  const label = getPurchaseModeLabel(modeType);

  return (
    <div className="purchase-mode-allocation-input">
      <div className="purchase-mode-allocation-input__top">
        <span className="purchase-mode-allocation-input__label">{label}</span>
        <span className="purchase-mode-allocation-input__status">{statusMessage}</span>
      </div>

      <div className="purchase-mode-allocation-input__summary">
        {`实际 ${actualCount} / 配置 ${targetCount}`}
      </div>

      <div className="purchase-mode-allocation-input__controls">
        <button
          aria-label={`${label} 减少实际分配`}
          className="ghost-button purchase-mode-allocation-input__step"
          disabled={disabled || !canDecrease}
          type="button"
          onClick={() => {
            onDecrease?.();
          }}
        >
          -
        </button>

        <div className="purchase-mode-allocation-input__value">{actualCount}</div>

        <button
          aria-label={`${label} 增加实际分配`}
          className="ghost-button purchase-mode-allocation-input__step"
          disabled={disabled || !canIncrease}
          type="button"
          onClick={() => {
            onIncrease?.();
          }}
        >
          +
        </button>
      </div>

      <div className="purchase-mode-allocation-input__meta">{`共享余量 ${sharedAvailableCount}`}</div>
    </div>
  );
}
