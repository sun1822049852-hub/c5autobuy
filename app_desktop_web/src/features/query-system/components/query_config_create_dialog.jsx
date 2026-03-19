export function QueryConfigCreateDialog({
  form,
  isOpen,
  isSubmitting,
  onClose,
  onFieldChange,
  onSubmit,
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
        aria-label="新建配置"
        className="dialog-surface query-config-dialog"
        role="dialog"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit?.();
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title">新建配置</h2>
            <p className="surface-subtitle">配置创建后立即入库，商品和阈值继续在右侧工作台编辑。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">配置名称</span>
            <input
              className="form-input"
              type="text"
              value={form.name}
              aria-label="配置名称"
              onChange={(event) => onFieldChange("name", event.target.value)}
            />
          </label>

          <label className="form-field">
            <span className="form-label">配置说明</span>
            <input
              className="form-input"
              type="text"
              value={form.description}
              aria-label="配置说明"
              onChange={(event) => onFieldChange("description", event.target.value)}
            />
          </label>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit" disabled={isSubmitting || !String(form.name || "").trim()}>
            {isSubmitting ? "保存中..." : "保存配置"}
          </button>
        </div>
      </form>
    </div>
  );
}
