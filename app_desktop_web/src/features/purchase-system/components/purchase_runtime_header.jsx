export function PurchaseRuntimeHeader({
  activeQueryConfig,
  configActionLabel,
  displayConfigName,
  isLoading,
  isPurchaseSettingsLoading,
  isQuerySettingsLoading,
  onOpenConfigDialog,
  onOpenPurchaseSettings,
  onOpenQuerySettings,
  runtimeMessage,
  totalPurchasedCount,
}) {
  const configName = displayConfigName || activeQueryConfig?.config_name || "未选择配置";
  const stateText = isLoading ? "加载中..." : (runtimeMessage || "未运行");

  return (
    <section aria-label="扫货运行控制台" className="purchase-runtime-header">
      <div className="purchase-runtime-header__primary">
        <div className="purchase-runtime-header__eyebrow">当前配置</div>
        <div className="purchase-runtime-header__name-row">
          <div className="purchase-runtime-header__name">{configName}</div>
          <div className="purchase-runtime-header__status">{stateText}</div>
        </div>
      </div>

      <div className="purchase-runtime-header__inline-actions">
        <button
          className="ghost-button purchase-runtime-header__config-button"
          disabled={isPurchaseSettingsLoading}
          type="button"
          onClick={() => {
            onOpenPurchaseSettings?.();
          }}
        >
          {isPurchaseSettingsLoading ? "加载设置..." : "购买设置"}
        </button>

        <button
          className="ghost-button purchase-runtime-header__config-button"
          disabled={isQuerySettingsLoading}
          type="button"
          onClick={() => {
            onOpenQuerySettings?.();
          }}
        >
          {isQuerySettingsLoading ? "加载设置..." : "查询设置"}
        </button>

        <button
          className="ghost-button purchase-runtime-header__config-button"
          type="button"
          onClick={() => {
            onOpenConfigDialog?.();
          }}
        >
          {configActionLabel}
        </button>

        <div className="purchase-runtime-header__meta-row">
          <div className="purchase-runtime-header__meta-block">
            <div className="purchase-runtime-header__meta-label">累计购买</div>
            <div className="purchase-runtime-header__meta-value">{totalPurchasedCount}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
