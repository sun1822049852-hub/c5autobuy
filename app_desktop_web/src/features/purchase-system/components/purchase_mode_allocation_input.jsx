const MODE_LABELS = {
  new_api: "api查询器",
  fast_api: "api高速查询器",
  token: "浏览器查询器",
};


export function getPurchaseModeLabel(modeType) {
  return MODE_LABELS[modeType] || modeType || "未知查询器";
}


export function PurchaseModeAllocationInput({
  disabled = false,
  modeType,
  overflowCount = 0,
  remainingCount = 0,
  statusMessage = "未运行",
  value,
  onChange,
}) {
  const label = getPurchaseModeLabel(modeType);

  return (
    <label className="purchase-mode-allocation-input">
      <div className="purchase-mode-allocation-input__top">
        <span className="purchase-mode-allocation-input__label">{label}</span>
        <span className="purchase-mode-allocation-input__status">{statusMessage}</span>
      </div>

      <div className="purchase-mode-allocation-input__body">
        <input
          className="purchase-mode-allocation-input__field"
          type="number"
          min="0"
          step="1"
          value={value}
          disabled={disabled}
          aria-label={`${label} 目标分配数`}
          onChange={(event) => onChange(event.target.value)}
        />

        <span className={`purchase-mode-allocation-input__meta${overflowCount > 0 ? " is-danger" : ""}`}>
          {overflowCount > 0 ? `${label} 已超出 ${overflowCount}` : `${label} 还可分配 ${remainingCount}`}
        </span>
      </div>
    </label>
  );
}
