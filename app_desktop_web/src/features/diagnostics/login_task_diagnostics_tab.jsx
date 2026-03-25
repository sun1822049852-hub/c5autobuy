import { getEventDetailLines } from "../../shared/feedback_details.js";
import { DiagnosticsSummary } from "./diagnostics_summary.jsx";


export function LoginTaskDiagnosticsTab({ snapshot }) {
  return (
    <div className="diagnostics-tab">
      <DiagnosticsSummary
        items={[
          { label: "进行中", value: String(snapshot.running_count || 0) },
          { label: "冲突", value: String(snapshot.conflict_count || 0) },
          { label: "失败", value: String(snapshot.failed_count || 0), tone: snapshot.failed_count ? "danger" : "muted" },
        ]}
      />

      <section className="diagnostics-section" aria-label="最近登录任务">
        <header className="diagnostics-section__header">
          <h3 className="diagnostics-section__title">最近登录任务</h3>
        </header>
        {snapshot.recent_tasks?.length ? (
          <div className="diagnostics-row-list">
            {snapshot.recent_tasks.map((task) => (
              <article key={task.task_id} className={`diagnostics-row${task.state === "failed" ? " is-danger" : ""}`}>
                <div className="diagnostics-row__top">
                  <strong>{task.account_display_name || task.account_id || task.task_id}</strong>
                  <span>{task.state}</span>
                </div>
                <div className="diagnostics-row__meta">{task.last_message || "无进度信息"}</div>
                <div className="diagnostics-timeline">
                  {task.events?.map((event) => (
                    <div key={`${task.task_id}-${event.timestamp}-${event.state}`} className="diagnostics-timeline__item">
                      <span className="diagnostics-timeline__state">{event.state}</span>
                      <span className="diagnostics-timeline__message">{event.message || event.timestamp}</span>
                      {getEventDetailLines(event).length ? (
                        <div className="diagnostics-timeline__details">
                          {getEventDetailLines(event).map((line, detailIndex) => (
                            <div
                              key={`${task.task_id}-${event.timestamp}-${line}-${detailIndex}`}
                              className="diagnostics-timeline__detail"
                            >
                              {line}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="diagnostics-empty">暂无登录任务</div>
        )}
      </section>
    </div>
  );
}
