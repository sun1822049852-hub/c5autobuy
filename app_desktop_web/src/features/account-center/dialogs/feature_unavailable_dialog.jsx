export function FeatureUnavailableDialog({
  isOpen = false,
  message = "当前此功能未开放",
  onClose,
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
      <section aria-label="功能未开放" className="dialog-surface" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">功能未开放</h2>
            <p className="surface-subtitle">当前账号暂时无法开启这项功能。</p>
          </div>
          <button className="ghost-button" type="button" onClick={() => onClose?.()}>
            关闭
          </button>
        </div>
        <div className="account-delete-dialog__body">
          <p>{message}</p>
        </div>
        <div className="surface-actions">
          <button className="accent-button" type="button" onClick={() => onClose?.()}>
            知道了
          </button>
        </div>
      </section>
    </div>
  );
}
