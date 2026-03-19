export function PurchaseItemPanel({ row }) {
  const itemName = row.item_name || row.query_item_id;
  const wearText = `${row.detail_min_wear ?? row.min_wear ?? "-"} ~ ${row.detail_max_wear ?? row.max_wear ?? "-"}`;

  return (
    <section className="purchase-item-panel" aria-label={`商品 ${itemName}`}>
      <div className="purchase-item-panel__name">{itemName}</div>
      <div className="purchase-item-panel__meta">
        价格 {row.max_price ?? "-"} | 磨损 {wearText}
      </div>
      <div className="purchase-item-panel__stats">
        <span>查询 {row.query_execution_count} 次</span>
        <span>命中 {row.matched_product_count}</span>
        <span>成功 {row.purchase_success_count}</span>
        <span>失败 {row.purchase_failed_count}</span>
      </div>
    </section>
  );
}
