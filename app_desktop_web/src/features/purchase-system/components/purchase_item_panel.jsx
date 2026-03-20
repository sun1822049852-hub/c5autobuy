import { useState } from "react";


export function PurchaseItemPanel({ row }) {
  const [expanded, setExpanded] = useState(false);
  const itemName = row.item_name || row.query_item_id;
  const wearText = `${row.detail_min_wear ?? row.min_wear ?? "-"} ~ ${row.detail_max_wear ?? row.max_wear ?? "-"}`;
  const detailId = `purchase-item-panel-${row.query_item_id}`;

  return (
    <section className="purchase-item-panel">
      <button
        aria-controls={detailId}
        aria-expanded={expanded ? "true" : "false"}
        aria-label={itemName}
        className="purchase-item-panel__toggle"
        type="button"
        onClick={() => {
          setExpanded((current) => !current);
        }}
      >
        <div className="purchase-item-panel__toggle-main">
          <div className="purchase-item-panel__name">{itemName}</div>
          <div className="purchase-item-panel__hint">{expanded ? "收起详情" : "展开详情"}</div>
        </div>
        <div className="purchase-item-panel__stats">
          <span className="purchase-item-panel__stat">已查 {row.query_execution_count ?? 0}</span>
          <span className="purchase-item-panel__stat">已命中 {row.matched_product_count ?? 0}</span>
          <span className="purchase-item-panel__stat">已成功 {row.purchase_success_count ?? 0}</span>
          <span className="purchase-item-panel__stat">已失败 {row.purchase_failed_count ?? 0}</span>
        </div>
      </button>

      {expanded ? (
        <div className="purchase-item-panel__detail" id={detailId}>
          <div className="purchase-item-panel__detail-card">价格阈值 {row.max_price ?? "-"}</div>
          <div className="purchase-item-panel__detail-card">磨损 {wearText}</div>
          <div className="purchase-item-panel__detail-card">查询 {row.query_execution_count ?? 0}</div>
          <div className="purchase-item-panel__detail-card">命中 {row.matched_product_count ?? 0}</div>
          <div className="purchase-item-panel__detail-card">成功 {row.purchase_success_count ?? 0}</div>
          <div className="purchase-item-panel__detail-card">失败 {row.purchase_failed_count ?? 0}</div>
        </div>
      ) : null}
    </section>
  );
}
