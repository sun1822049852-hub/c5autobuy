export function QuerySaveBar({
  disabled,
  isRuntimeActionPending,
  isSaving,
  message,
  onRuntimeAction,
  onSave,
  runtimeActionDisabled,
  runtimeActionLabel,
}) {
  return (
    <section className="query-save-bar">
      <div className="query-save-bar__copy">
        <div className="query-save-bar__title">保存区</div>
        <div className="query-save-bar__subtitle">{message}</div>
      </div>
      <div className="query-save-bar__actions">
        <button
          className="ghost-button"
          type="button"
          disabled={runtimeActionDisabled}
          onClick={onRuntimeAction}
        >
          {isRuntimeActionPending ? "处理中..." : runtimeActionLabel}
        </button>
        <button className="accent-button" type="button" disabled={disabled} onClick={onSave}>
          {isSaving ? "保存中..." : "保存当前配置"}
        </button>
      </div>
    </section>
  );
}
