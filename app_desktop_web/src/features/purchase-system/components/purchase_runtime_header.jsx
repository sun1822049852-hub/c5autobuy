export function PurchaseRuntimeHeader({
  activeQueryConfig,
  isLoading,
  matchedProductCount,
  purchaseFailedCount,
  purchaseSuccessCount,
  runtimeMessage,
}) {
  return (
    <section className="purchase-runtime-header">
      <div className="purchase-runtime-header__config">
        <div className="purchase-runtime-header__label">当前绑定配置</div>
        <div className="purchase-runtime-header__name">
          {activeQueryConfig?.config_name || "当前未绑定查询配置"}
        </div>
        <div className="purchase-runtime-header__meta">
          {isLoading ? "加载中..." : runtimeMessage}
        </div>
      </div>
      <div className="purchase-runtime-header__stats" aria-label="购买统计摘要">
        <div className="purchase-runtime-header__stat">matched {matchedProductCount}</div>
        <div className="purchase-runtime-header__stat">success {purchaseSuccessCount}</div>
        <div className="purchase-runtime-header__stat">failed {purchaseFailedCount}</div>
      </div>
    </section>
  );
}
