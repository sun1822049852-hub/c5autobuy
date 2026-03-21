import { useState } from "react";

import {
  getPurchaseModeLabel,
  PurchaseModeAllocationInput,
} from "./purchase_mode_allocation_input.jsx";


const MODE_ORDER = ["new_api", "fast_api", "token"];


function formatSourceModeLabel(source) {
  return getPurchaseModeLabel(source?.mode_type);
}


function saveFeedbackClassName(saveState) {
  if (!saveState?.message) {
    return "purchase-item-panel__save-feedback";
  }

  if (saveState.status === "error" || saveState.status === "failed_after_save") {
    return "purchase-item-panel__save-feedback is-danger";
  }

  return "purchase-item-panel__save-feedback is-success";
}


export function PurchaseItemPanel({
  onAllocationChange,
  onManualPausedChange,
  onSave,
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
  const saveState = row.saveState || null;
  const isSaving = Boolean(saveState?.pending);

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
            <div className="purchase-item-panel__summary-line">价格 &lt;= {row.max_price ?? "-"}</div>
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
              <div className="purchase-item-panel__detail-copy">选择真实配置后，这里会显示查询分配与热应用控制。</div>
            ) : (
              <>
                <div className="purchase-item-panel__allocation-grid">
                  {MODE_ORDER.map((modeType) => (
                    <PurchaseModeAllocationInput
                      key={modeType}
                      disabled={isSaving}
                      modeType={modeType}
                      overflowCount={row.remainingByMode?.[modeType]?.overflowCount ?? 0}
                      remainingCount={row.remainingByMode?.[modeType]?.remainingCount ?? 0}
                      statusMessage={row.statusByMode?.[modeType]?.status_message ?? "未运行"}
                      value={row.draft?.modeAllocations?.[modeType] ?? 0}
                      onChange={(value) => onAllocationChange?.(row.query_item_id, modeType, value)}
                    />
                  ))}
                </div>

                <label className="purchase-item-panel__pause-toggle">
                  <input
                    type="checkbox"
                    checked={Boolean(row.draft?.manualPaused)}
                    aria-label={`${itemName} 手动暂停`}
                    disabled={isSaving}
                    onChange={(event) => onManualPausedChange?.(row.query_item_id, event.target.checked)}
                  />
                  <span>手动暂停该商品</span>
                </label>

                {saveState?.message ? (
                  <div className={saveFeedbackClassName(saveState)}>{saveState.message}</div>
                ) : null}

                <div className="purchase-item-panel__actions">
                  <button
                    className="accent-button purchase-item-panel__save-button"
                    disabled={isSaving}
                    type="button"
                    onClick={() => onSave?.(row.query_item_id)}
                  >
                    {isSaving ? "保存中..." : "保存分配"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
