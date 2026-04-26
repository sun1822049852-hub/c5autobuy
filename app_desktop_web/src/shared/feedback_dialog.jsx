export function FeedbackDialog({
  actionLabel = "知道了",
  isOpen = false,
  message = "",
  onClose = null,
  title = "操作提示",
}) {
  if (!isOpen || !message) {
    return null;
  }

  return (
    <div className="surface-backdrop" role="presentation">
      <section
        aria-label={title}
        aria-modal="true"
        className="dialog-surface feedback-dialog"
        role="dialog"
      >
        <div className="surface-header feedback-dialog__header">
          <div>
            <div className="feedback-dialog__eyebrow">提示</div>
            <h2 className="surface-title">{title}</h2>
          </div>
        </div>

        <p className="feedback-dialog__message">{message}</p>

        {typeof onClose === "function" ? (
          <div className="surface-actions feedback-dialog__actions">
            <button className="accent-button" type="button" onClick={onClose}>
              {actionLabel}
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
