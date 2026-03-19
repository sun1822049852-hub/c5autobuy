export function QueryModeAllocationInput({
  disabled = false,
  modeType,
  overflowCount = 0,
  remainingCount = 0,
  value,
  onChange,
}) {
  return (
    <label className="query-mode-allocation-input">
      <span className="query-mode-allocation-input__label">{modeType} 专属目标</span>
      <input
        className="query-mode-allocation-input__field"
        type="number"
        min="0"
        step="1"
        value={value}
        disabled={disabled}
        aria-label={`${modeType} 专属目标`}
        onChange={(event) => onChange(event.target.value)}
      />
      <span className={`query-mode-allocation-input__meta${overflowCount > 0 ? " is-danger" : ""}`}>
        {overflowCount > 0 ? `${modeType} 已超出 ${overflowCount}` : `${modeType} 还可分配 ${remainingCount}`}
      </span>
    </label>
  );
}
