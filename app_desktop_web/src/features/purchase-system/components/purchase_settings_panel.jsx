export function PurchaseSettingsPanel({
  error,
  fanoutLimit,
  maxInflightPerAccount,
  notice,
  isPending,
  isSaving,
  onSave,
  onFanoutLimitChange,
  onMaxInflightPerAccountChange,
}) {
  return (
    <section aria-label="购买设置" className="purchase-settings-panel">
      <div className="purchase-settings-panel__header">
        <div>
          <h2 className="purchase-settings-panel__title">购买设置</h2>
          <p className="purchase-settings-panel__subtitle">控制单批次命中时每个购买 IP 的派发账号数，以及单个购买账号可同时执行的购买任务数。</p>
        </div>
      </div>

      <label className="form-field purchase-settings-panel__field" htmlFor="purchase-fanout-limit">
        <span className="form-label">单批次单IP并发购买数</span>
        <input
          id="purchase-fanout-limit"
          aria-label="单批次单IP并发购买数"
          className="form-input"
          disabled={isPending}
          min="1"
          step="1"
          type="number"
          value={fanoutLimit}
          onChange={(event) => {
            onFanoutLimitChange?.(event.target.value);
          }}
        />
        <span className="form-hint">默认值为 1。每个购买 IP 在一次命中批次里最多派发这么多个当前空闲账号。</span>
      </label>

      <label className="form-field purchase-settings-panel__field" htmlFor="purchase-max-inflight-per-account">
        <span className="form-label">单账号最大并发购买任务数</span>
        <input
          id="purchase-max-inflight-per-account"
          aria-label="单账号最大并发购买任务数"
          className="form-input"
          disabled={isPending}
          min="1"
          step="1"
          type="number"
          value={maxInflightPerAccount}
          onChange={(event) => {
            onMaxInflightPerAccountChange?.(event.target.value);
          }}
        />
        <span className="form-hint">默认值为 1。单个购买账号最多同时执行这么多个购买任务；若当前已有任务在跑，新值会在本次购买完成后生效。</span>
      </label>

      {error ? <div className="purchase-settings-panel__error">{error}</div> : null}
      {notice ? <div className="purchase-settings-panel__notice">{notice}</div> : null}

      <div className="purchase-settings-panel__actions">
        <button
          className="accent-button"
          disabled={isPending || !isSaving}
          type="button"
          onClick={() => {
            onSave?.();
          }}
        >
          {isPending ? "保存中..." : "保存购买设置"}
        </button>
      </div>
    </section>
  );
}
