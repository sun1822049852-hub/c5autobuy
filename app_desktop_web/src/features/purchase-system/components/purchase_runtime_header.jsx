function PurchaseHeaderMetric({ accent = false, label, value }) {
  return (
    <div className={`purchase-runtime-header__stat-card${accent ? " purchase-runtime-header__stat-card--accent" : ""}`}>
      <div className="purchase-runtime-header__stat-value">{value}</div>
      <div className="purchase-runtime-header__stat-label">{label}</div>
    </div>
  );
}


function formatRuntimeSession(runtimeSessionId) {
  if (!runtimeSessionId) {
    return "未建立";
  }

  return runtimeSessionId.length <= 18
    ? runtimeSessionId
    : runtimeSessionId.slice(-18);
}


export function PurchaseRuntimeHeader({
  activeAccountCount,
  activeQueryConfig,
  isLoading,
  matchedProductCount,
  queueSize,
  purchaseFailedCount,
  purchaseSuccessCount,
  runtimeSessionId,
  runtimeMessage,
  totalAccountCount,
  totalPurchasedCount,
}) {
  const configName = activeQueryConfig?.config_name || "当前未绑定查询配置";
  const stateText = isLoading ? "加载中..." : (runtimeMessage || "未运行");

  return (
    <section aria-label="购买运行控制台" className="purchase-runtime-header">
      <div className="purchase-runtime-header__primary">
        <div className="purchase-runtime-header__eyebrow">Purchase Runtime</div>
        <div className="purchase-runtime-header__name-row">
          <div className="purchase-runtime-header__name">{configName}</div>
          <div className="purchase-runtime-header__status">{stateText}</div>
        </div>
        <div className="purchase-runtime-header__meta-row">
          <div className="purchase-runtime-header__meta-block">
            <div className="purchase-runtime-header__meta-label">运行代号</div>
            <div className="purchase-runtime-header__meta-value">{formatRuntimeSession(runtimeSessionId)}</div>
          </div>
          <div className="purchase-runtime-header__meta-block">
            <div className="purchase-runtime-header__meta-label">累计购买</div>
            <div className="purchase-runtime-header__meta-value">{totalPurchasedCount}</div>
          </div>
        </div>
      </div>

      <div className="purchase-runtime-header__stats" aria-label="购买运行摘要">
        <PurchaseHeaderMetric label="队列中" value={queueSize} />
        <PurchaseHeaderMetric label="活跃账号" value={`${activeAccountCount}/${totalAccountCount}`} />
        <PurchaseHeaderMetric accent label={`真实命中 ${matchedProductCount}`} value="实时" />
        <PurchaseHeaderMetric accent label={`购买成功 ${purchaseSuccessCount}`} value="已购" />
        <PurchaseHeaderMetric accent label={`购买失败 ${purchaseFailedCount}`} value="回执" />
      </div>
    </section>
  );
}
