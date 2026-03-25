export function UnsavedChangesDialog({
  error,
  isOpen,
  isSaving,
  onDiscard,
  onSave,
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="surface-backdrop" role="presentation">
      <section aria-label="未保存修改" className="dialog-surface query-leave-dialog" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">未保存修改</h2>
            <p className="surface-subtitle">当前修改尚未保存，离开前选择保存或直接丢弃。</p>
          </div>
        </div>

        {error ? <div className="query-workbench-header__save-message is-danger">{error}</div> : null}

        <div className="surface-actions">
          <button className="danger-button" type="button" disabled={isSaving} onClick={onDiscard}>
            不保存
          </button>
          <button className="accent-button" type="button" disabled={isSaving} onClick={onSave}>
            {isSaving ? "保存中..." : "保存"}
          </button>
        </div>
      </section>
    </div>
  );
}
