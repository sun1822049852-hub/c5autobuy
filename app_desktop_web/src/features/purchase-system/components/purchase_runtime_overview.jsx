function PurchaseOverviewCard({ label, value }) {
  return (
    <div className="purchase-runtime-overview__card">
      <div className="purchase-runtime-overview__card-label">{label}</div>
      <div className="purchase-runtime-overview__card-value">{value}</div>
    </div>
  );
}


export function PurchaseRuntimeOverview({
  activeAccountCount,
  queueSize,
  totalAccountCount,
  totalPurchasedCount,
}) {
  return (
    <section aria-label="运行总览" className="purchase-runtime-overview">
      <h2 className="purchase-runtime-overview__title">运行总览</h2>
      <div className="purchase-runtime-overview__grid">
        <PurchaseOverviewCard label="队列中" value={queueSize} />
        <PurchaseOverviewCard label="活跃账号" value={`${activeAccountCount}/${totalAccountCount}`} />
        <PurchaseOverviewCard label="累计购买" value={totalPurchasedCount} />
      </div>
    </section>
  );
}
