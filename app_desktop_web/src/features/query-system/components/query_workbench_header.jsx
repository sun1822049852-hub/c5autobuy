function getSaveButtonToneClass({
  currentConfig,
  hasUnsavedChanges,
  isSaving,
  saveError,
}) {
  if (saveError) {
    return "is-danger";
  }
  if (!currentConfig) {
    return "is-idle";
  }
  if (isSaving) {
    return "is-saving";
  }
  if (hasUnsavedChanges) {
    return "is-warn";
  }
  return "is-success";
}


export function QueryWorkbenchHeader({
  capacityModes,
  currentConfig,
  currentStatusText,
  hasUnsavedChanges,
  isLoading,
  isSaving,
  onSave,
  runtimeMessage,
  saveDisabled,
  saveError,
  saveLabel,
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
          className={`ghost-button query-workbench-header__save-button ${getSaveButtonToneClass({
            currentConfig,
            hasUnsavedChanges,
            isSaving,
            saveError,
          })}`.trim()}
          type="button"
          disabled={saveDisabled}
          onClick={onSave}
        >
          {saveLabel}
        </button>
      </div>

      {saveError ? (
        <div className="query-workbench-header__footer">
          <div className="query-workbench-header__save-message is-danger">{saveError}</div>
        </div>
      ) : null}
    </section>
  );
}
