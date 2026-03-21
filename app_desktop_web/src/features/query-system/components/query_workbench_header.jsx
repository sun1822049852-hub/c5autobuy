function getSaveToneClass(saveMessage) {
  if (String(saveMessage || "").includes("失败")) {
    return "is-danger";
  }
  if (String(saveMessage || "").includes("未保存")) {
    return "is-warn";
  }
  return "is-success";
}


export function QueryWorkbenchHeader({
  capacityModes,
  currentConfig,
  currentStatusText,
  isLoading,
  isSaving,
  onSave,
  runtimeMessage,
  saveDisabled,
  saveMessage,
}) {
  return (
    <section className="query-workbench-header">
      <div className="query-workbench-header__topline">
        <div className="query-workbench-header__identity">
          <h2 className="query-workbench-header__title">
            {isLoading ? "正在载入配置..." : (currentConfig?.name || "未选择配置")}
          </h2>
          <span className="query-workbench-header__label">当前配置</span>
          <div className="query-workbench-header__capacity">
            {capacityModes.map((mode) => (
              <span key={mode.mode_type} className="query-workbench-header__capacity-chip">
                {mode.mode_type} {mode.available_account_count}
              </span>
            ))}
          </div>
          <div className="query-workbench-header__runtime">
            <span className="query-workbench-header__status">{currentStatusText}</span>
            <span className="query-workbench-header__runtime-text">{runtimeMessage}</span>
          </div>
        </div>

        <button
          className="ghost-button query-workbench-header__save-button"
          type="button"
          disabled={saveDisabled}
          onClick={onSave}
        >
          {isSaving ? "保存中..." : "保存当前配置"}
        </button>
      </div>

      <div className="query-workbench-header__footer">
        <div className={`query-workbench-header__save-message ${getSaveToneClass(saveMessage)}`.trim()}>{saveMessage}</div>
      </div>
    </section>
  );
}
