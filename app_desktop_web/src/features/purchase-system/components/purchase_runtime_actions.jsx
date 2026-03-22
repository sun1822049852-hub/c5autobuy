export function PurchaseRuntimeActions({
  actionLabel,
  isSubmitDisabled,
  isActionDisabled,
  isPending,
  isSubmitPending,
  onAction,
  onOpenAccountDetails,
  onOpenRecentEvents,
  onSubmitChanges,
}) {
  return (
    <section aria-label="扫货运行动作" className="purchase-runtime-actions">
      <div className="purchase-runtime-actions__surface">
        <div className="purchase-runtime-actions__buttons">
          <button
            className="ghost-button purchase-runtime-actions__button purchase-runtime-actions__button--secondary"
            type="button"
            onClick={() => {
              onOpenRecentEvents?.();
            }}
          >
            最近事件
          </button>

          <button
            className="ghost-button purchase-runtime-actions__button purchase-runtime-actions__button--secondary"
            type="button"
            onClick={() => {
              onOpenAccountDetails?.();
            }}
          >
            查看账号详情
          </button>

          <button
            className="ghost-button purchase-runtime-actions__button purchase-runtime-actions__button--secondary"
            disabled={isSubmitDisabled}
            type="button"
            onClick={() => {
              onSubmitChanges?.();
            }}
          >
            {isSubmitPending ? "提交中..." : "提交更改"}
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
