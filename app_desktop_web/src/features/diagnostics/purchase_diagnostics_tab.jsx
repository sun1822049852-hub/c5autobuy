import { DiagnosticsEventList } from "./diagnostics_event_list.jsx";
import { DiagnosticsSummary } from "./diagnostics_summary.jsx";


export function PurchaseDiagnosticsTab({ snapshot }) {
  return (
    <div className="diagnostics-tab">
      <DiagnosticsSummary
        items={[
          { label: "状态", value: snapshot.running ? snapshot.message || "运行中" : "未运行" },
          { label: "活跃账号", value: String(snapshot.active_account_count || 0) },
          { label: "购买成功", value: String(snapshot.total_purchased_count || 0) },
          { label: "最近错误", value: snapshot.last_error || "无", tone: snapshot.last_error ? "danger" : "muted" },
        ]}
      />

      <section className="diagnostics-section" aria-label="异常购买账号">
        <header className="diagnostics-section__header">
          <h3 className="diagnostics-section__title">异常购买账号</h3>
        </header>
        {snapshot.account_rows?.length ? (
          <div className="diagnostics-row-list">
            {snapshot.account_rows.map((row) => (
              <article key={row.account_id} className={`diagnostics-row${row.last_error ? " is-danger" : ""}`}>
                <div className="diagnostics-row__top">
                  <strong>{row.display_name || row.account_id}</strong>
                  <span>{row.purchase_pool_state || "未知"}</span>
                </div>
                <div className="diagnostics-row__meta">
                  仓库 {row.selected_inventory_name || "未选择"} · 剩余 {row.selected_inventory_remaining_capacity ?? "-"}
                </div>
                {row.last_error ? <div className="diagnostics-row__error">{row.last_error}</div> : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="diagnostics-empty">暂无异常购买账号</div>
        )}
      </section>

      <DiagnosticsEventList
        rows={snapshot.recent_events || []}
        timeKey="occurred_at"
        title="最近购买事件"
      />
    </div>
  );
}
