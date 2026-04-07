import { useState } from "react";

import { DiagnosticsSummary } from "./diagnostics_summary.jsx";
import { QueryEventsModal } from "./query_events_modal.jsx";


export function QueryDiagnosticsTab({ snapshot }) {
  const [showEvents, setShowEvents] = useState(false);
  const events = snapshot.recent_events || [];

  return (
    <div className="diagnostics-tab">
      <DiagnosticsSummary
        items={[
          { label: "当前配置", value: snapshot.config_name || "未运行" },
          { label: "查询次数", value: String(snapshot.total_query_count || 0) },
          { label: "命中数量", value: String(snapshot.total_found_count || 0) },
          { label: "最近错误", value: snapshot.last_error || "无", tone: snapshot.last_error ? "danger" : "muted" },
        ]}
      />

      <section className="diagnostics-section" aria-label="查询模式">
        <header className="diagnostics-section__header">
          <h3 className="diagnostics-section__title">查询模式</h3>
        </header>
        <div className="diagnostics-row-list">
          {snapshot.mode_rows?.map((row) => (
            <article key={row.mode_type} className={`diagnostics-row${row.last_error ? " is-danger" : ""}`}>
              <div className="diagnostics-row__top">
                <strong>{row.mode_type}</strong>
                <span>{row.query_count} 次</span>
              </div>
              <div className="diagnostics-row__meta">
                可用 {row.eligible_account_count} · 活跃 {row.active_account_count} · 命中 {row.found_count}
              </div>
              {row.last_error ? <div className="diagnostics-row__error">{row.last_error}</div> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="diagnostics-section" aria-label="异常查询账号">
        <header className="diagnostics-section__header">
          <h3 className="diagnostics-section__title">异常查询账号</h3>
        </header>
        {snapshot.account_rows?.length ? (
          <div className="diagnostics-row-list">
            {snapshot.account_rows.map((row) => (
              <article key={row.account_id} className="diagnostics-row is-danger">
                <div className="diagnostics-row__top">
                  <strong>{row.display_name || row.account_id}</strong>
                  <span>{row.mode_type}</span>
                </div>
                <div className="diagnostics-row__meta">
                  查询 {row.query_count} · 命中 {row.found_count} · 最近 {row.last_seen_at || "未知"}
                </div>
                <div className="diagnostics-row__error">{row.last_error || row.disabled_reason || "异常"}</div>
              </article>
            ))}
          </div>
        ) : (
          <div className="diagnostics-empty">暂无异常查询账号</div>
        )}
      </section>

      {/* 事件日志入口按钮 */}
      <button
        type="button"
        className="query-events-trigger"
        onClick={() => setShowEvents(true)}
      >
        <span>查询事件日志</span>
        <span className="query-events-trigger__badge">{events.length}</span>
      </button>

      {showEvents ? (
        <QueryEventsModal events={events} onClose={() => setShowEvents(false)} />
      ) : null}
    </div>
  );
}

