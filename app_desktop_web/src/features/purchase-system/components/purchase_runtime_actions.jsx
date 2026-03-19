export function PurchaseRuntimeActions({ actionLabel, isPending, onAction }) {
  return (
    <div className="purchase-runtime-actions">
      <button
        className="accent-button purchase-runtime-actions__button"
        disabled={isPending}
        type="button"
        onClick={() => {
          onAction?.();
        }}
      >
        {isPending ? "处理中..." : actionLabel}
      </button>
    </div>
  );
}
