import { useState } from "react";

import {
  getPurchaseModeLabel,
  PurchaseModeAllocationInput,
} from "./purchase_mode_allocation_input.jsx";


const MODE_ORDER = ["new_api", "fast_api", "token"];


function formatSourceModeLabel(source) {
  const modeLabel = getPurchaseModeLabel(source?.mode_type);
  const accountLabel = String(source?.account_display_name || "").trim();
  return accountLabel ? `${accountLabel} / ${modeLabel}` : modeLabel;
}


export function PurchaseItemPanel({
  onDecreaseAllocation,
  onIncreaseAllocation,
  row,
}) {
  const [expanded, setExpanded] = useState(false);
  const isPreview = Boolean(row.is_preview);
  const itemName = row.item_name || row.query_item_id;
  const wearText = `${row.detail_min_wear ?? row.min_wear ?? "-"} ~ ${row.detail_max_wear ?? row.max_wear ?? "-"}`;
  const detailId = `purchase-item-panel-${row.query_item_id}`;
  const sourceStats = Array.isArray(row.source_mode_stats) ? row.source_mode_stats : [];
  const statItems = [
    { label: "查询次数", value: row.query_execution_count ?? 0 },
    { label: "命中", value: row.matched_product_count ?? 0 },
    { label: "成功", value: row.purchase_success_count ?? 0 },
    { label: "失败", value: row.purchase_failed_count ?? 0 },
  ];
  const modeRows = Array.isArray(row.mode_rows) ? row.mode_rows : [];

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
        <div className="purchase-item-panel__top-bar">
          <div className="purchase-item-panel__headline">
            <div className="purchase-item-panel__name">{itemName}</div>
            {isPreview ? (
              <div className="purchase-item-panel__summary-line purchase-item-panel__summary-line--preview">展示样例</div>
            ) : null}
            <div className="purchase-item-panel__summary-line">扫货价 &lt;= {row.max_price ?? "-"}</div>
            <div className="purchase-item-panel__summary-line">磨损 {wearText}</div>
          </div>
          <div className="purchase-item-panel__stats">
            {statItems.map((stat) => (
              <span key={stat.label} className="purchase-item-panel__stat">
                <span className="purchase-item-panel__stat-label">{stat.label}</span>
                <span className="purchase-item-panel__stat-value">{stat.value}</span>
              </span>
            ))}
          </div>
        </div>
      </button>

      {expanded ? (
        <div className="purchase-item-panel__detail" id={detailId}>
          <div className="purchase-item-panel__detail-card">
            <div className="purchase-item-panel__detail-title">命中来源</div>
            {sourceStats.length ? (
              <div className="purchase-item-panel__source-list">
                {sourceStats.map((source, index) => (
                  <article
                    key={`${source.account_id || "source"}-${source.mode_type || "mode"}-${index}`}
                    className="purchase-item-panel__source-item"
                  >
                    <div className="purchase-item-panel__source-name">{formatSourceModeLabel(source)}</div>
                    <div className="purchase-item-panel__source-count">{`命中 ${source.hit_count ?? 0}次`}</div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="purchase-item-panel__detail-copy">当前还没有命中来源。</div>
            )}
          </div>

          <div className="purchase-item-panel__detail-card">
            <div className="purchase-item-panel__detail-title">查询分配</div>
            {isPreview ? (
              <div className="purchase-item-panel__detail-copy">选择真实配置后，这里会显示运行时查询分配。</div>
            ) : (
              <div className="purchase-item-panel__allocation-grid">
                {MODE_ORDER.map((modeType) => {
                  const modeRow = modeRows.find((entry) => entry.mode_type === modeType);
                  return (
                    <PurchaseModeAllocationInput
                      key={modeType}
                      actualCount={modeRow?.actual_dedicated_count ?? 0}
                      canDecrease={Boolean(modeRow?.can_decrease)}
                      canIncrease={Boolean(modeRow?.can_increase)}
                      disabled={false}
                      modeType={modeType}
                      sharedAvailableCount={modeRow?.shared_available_count ?? 0}
                      statusMessage={modeRow?.status_message ?? "未运行"}
                      targetCount={modeRow?.target_dedicated_count ?? 0}
                      onDecrease={() => onDecreaseAllocation?.(row.query_item_id, modeType)}
                      onIncrease={() => onIncreaseAllocation?.(row.query_item_id, modeType)}
                    />
                  );
                })}
                </div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
