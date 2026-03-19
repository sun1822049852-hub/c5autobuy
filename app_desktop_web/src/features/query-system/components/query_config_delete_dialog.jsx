export function QueryConfigDeleteDialog({
  config,
  isDeleting,
  onClose,
  onConfirm,
}) {
  if (!config) {
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
      <section aria-label="删除配置" className="dialog-surface query-config-delete-dialog" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">删除配置</h2>
            <p className="surface-subtitle">这会移除该配置及其商品项，执行前只做一次确认。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="query-config-delete-dialog__name">{config.name}</div>

        <div className="surface-actions">
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
          <button className="accent-button" type="button" disabled={isDeleting} onClick={onConfirm}>
            {isDeleting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </section>
    </div>
  );
}
