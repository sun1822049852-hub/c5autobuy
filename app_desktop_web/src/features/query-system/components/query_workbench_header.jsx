export function QueryWorkbenchHeader({
  capacityModes,
  currentConfig,
  currentStatusText,
  isLoading,
  onOpenCreateItemDialog,
  runtimeMessage,
}) {
  return (
    <section className="query-workbench-header">
      <div className="query-workbench-header__copy">
        <div className="query-workbench-header__eyebrow">当前配置</div>
        <h2 className="query-workbench-header__title">
          {isLoading ? "正在载入配置..." : (currentConfig?.name || "未选择配置")}
        </h2>
        <p className="query-workbench-header__subtitle">
          {currentConfig?.description || "左侧选择配置后，这里会承载商品、分配与运行态工作台。"}
        </p>
      </div>
      <div className="query-workbench-header__meta">
        <div className="query-workbench-header__status">{currentStatusText}</div>
        <div className="query-workbench-header__runtime">{runtimeMessage}</div>
        <button
          className="accent-button query-workbench-header__action"
          type="button"
          disabled={!currentConfig}
          onClick={onOpenCreateItemDialog}
        >
          添加商品
        </button>
        <div className="query-workbench-header__capacity">
          {capacityModes.map((mode) => (
            <div key={mode.mode_type} className="query-workbench-header__capacity-chip">
              {mode.mode_type} {mode.available_account_count}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
