export function PurchaseSettingsPanel({
  enabledAccountIds,
  isPending,
  isSaving,
  onSave,
  onToggleAccount,
  rows,
}) {
  const enabledIds = new Set((enabledAccountIds || []).map((item) => String(item)));

  return (
    <section aria-label="购买账号启用设置" className="purchase-settings-panel">
      <div className="purchase-settings-panel__header">
        <div>
          <h2 className="purchase-settings-panel__title">购买账号启用设置</h2>
          <p className="purchase-settings-panel__subtitle">勾选后账号会参与购买池，取消勾选会保存为禁用购买能力。</p>
        </div>
      </div>

      {(rows || []).length ? (
        <div className="purchase-settings-panel__list">
          {rows.map((row) => {
            const accountId = String(row.account_id);
            return (
              <label key={accountId} className="purchase-settings-panel__row">
                <input
                  checked={enabledIds.has(accountId)}
                  disabled={isPending}
                  type="checkbox"
                  onChange={() => {
                    onToggleAccount?.(accountId);
                  }}
                />
                <span className="purchase-settings-panel__row-label">
                  {row.display_name || accountId}
                </span>
              </label>
            );
          })}
        </div>
      ) : (
        <div className="purchase-settings-panel__empty">当前没有可配置的购买账号。</div>
      )}

      <div className="purchase-settings-panel__actions">
        <button
          className="accent-button"
          disabled={isPending || !rows?.length || !isSaving}
          type="button"
          onClick={() => {
            onSave?.();
          }}
        >
          {isPending ? "保存中..." : "保存账号购买配置"}
        </button>
      </div>
    </section>
  );
}
