export function PurchaseRuntimeActions({
  actionLabel,
  configActionLabel,
  configDisplayName,
  isActionDisabled,
  isPending,
  onAction,
  onOpenConfigDialog,
}) {
  return (
    <section aria-label="购买运行动作" className="purchase-runtime-actions">
      <div className="purchase-runtime-actions__surface">
        <div className="purchase-runtime-actions__copy">
          <div className="purchase-runtime-actions__label">当前配置</div>
          <div className="purchase-runtime-actions__value">{configDisplayName}</div>
        </div>

        <div className="purchase-runtime-actions__buttons">
          <button
            className="ghost-button purchase-runtime-actions__button purchase-runtime-actions__button--secondary"
            disabled={isPending}
            type="button"
            onClick={() => {
              onOpenConfigDialog?.();
            }}
          >
            {configActionLabel}
          </button>

          <button
            className="accent-button purchase-runtime-actions__button"
            disabled={isActionDisabled}
            type="button"
            onClick={() => {
              onAction?.();
            }}
          >
            {isPending ? "处理中..." : actionLabel}
          </button>
        </div>
      </div>
    </section>
  );
}
