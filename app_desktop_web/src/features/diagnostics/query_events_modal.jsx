import { useState } from "react";

import { DiagnosticsEventList } from "./diagnostics_event_list.jsx";


const MODE_TABS = [
  { id: "all",      label: "全部" },
  { id: "new_api",  label: "NEW_API" },
  { id: "fast_api", label: "FAST_API" },
  { id: "token",    label: "TOKEN" },
];


export function QueryEventsModal({ events = [], onClose }) {
  const [activeMode, setActiveMode] = useState("all");

  const filtered = activeMode === "all"
    ? events
    : events.filter((e) => e.mode_type === activeMode);

  return (
    <div className="surface-backdrop" role="dialog" aria-modal="true" aria-label="查询事件日志">
      <div className="query-events-modal">
        {/* 标题栏 */}
        <header className="query-events-modal__header">
          <div>
            <div className="diagnostics-panel__eyebrow">Events</div>
            <h2 className="query-events-modal__title">
              查询事件日志
              <span className="query-events-modal__count">{events.length}</span>
            </h2>
          </div>
          <button
            type="button"
            className="ghost-button"
            aria-label="关闭"
            onClick={onClose}
          >
            关闭
          </button>
        </header>

        {/* 模式切换 Tab */}
        <div className="query-events-modal__tabs" role="tablist" aria-label="按模式筛选">
          {MODE_TABS.map((tab) => {
            const count = tab.id === "all"
              ? events.length
              : events.filter((e) => e.mode_type === tab.id).length;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={tab.id === activeMode}
                className={`query-events-modal__tab${tab.id === activeMode ? " is-active" : ""}`}
                onClick={() => setActiveMode(tab.id)}
              >
                {tab.label}
                <span className="query-events-modal__tab-count">{count}</span>
              </button>
            );
          })}
        </div>

        {/* 事件列表（可滚动） */}
        <div className="query-events-modal__body">
          <DiagnosticsEventList
            rows={filtered}
            title=""
            emptyText="暂无事件"
          />
        </div>
      </div>
    </div>
  );
}
