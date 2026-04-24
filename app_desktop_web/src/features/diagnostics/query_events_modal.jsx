import { useCallback, useRef, useState } from "react";

import { DiagnosticsEventList } from "./diagnostics_event_list.jsx";
import { formatSourceModeLabel } from "../stats/stats_shared.js";


function normalizeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}


function isErrorEvent(event) {
  const level = normalizeText(event?.level || event?.status || event?.state).toLowerCase();
  const statusCode = Number(event?.status_code ?? event?.http_status ?? event?.response_status);

  return level === "error"
    || level === "failed"
    || level === "failure"
    || level === "conflict"
    || level === "cancelled"
    || Boolean(normalizeText(event?.error || event?.error_message))
    || (Number.isFinite(statusCode) && statusCode >= 400);
}


function buildFilterTabs(resolveMode) {
  return [
    { id: "all", label: "全部", matches: () => true },
    { id: "error", label: "错误", matches: (event) => isErrorEvent(event) },
    { id: "new_api", label: "NEW_API", matches: (event) => resolveMode(event) === "new_api" },
    { id: "fast_api", label: "FAST_API", matches: (event) => resolveMode(event) === "fast_api" },
    { id: "token", label: "TOKEN", matches: (event) => resolveMode(event) === "token" },
  ];
}


function RuntimeEventsModal({
  emptyText = "暂无事件",
  events = [],
  formatSourceLabel = null,
  onClose,
  resolveMode = (event) => event?.mode_type,
  timeKey = "timestamp",
  title,
}) {
  const [activeTab, setActiveTab] = useState("all");
  const bodyRef = useRef(null);
  const handleTabSelect = useCallback((tabId) => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = 0;
    }
    setActiveTab(tabId);
  }, []);
  const filterTabs = buildFilterTabs(resolveMode);
  const currentTab = filterTabs.find((tab) => tab.id === activeTab) || filterTabs[0];

  const filtered = events.filter((event) => currentTab.matches(event));

  return (
    <div className="surface-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="query-events-modal">
        {/* 标题栏 */}
        <header className="query-events-modal__header">
          <div>
            <div className="diagnostics-panel__eyebrow">Events</div>
            <h2 className="query-events-modal__title">
              {title}
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
          {filterTabs.map((tab) => {
            const count = events.filter((event) => tab.matches(event)).length;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={tab.id === activeTab}
                className={`query-events-modal__tab${tab.id === activeTab ? " is-active" : ""}`}
                onClick={() => handleTabSelect(tab.id)}
              >
                {tab.label}
                <span className="query-events-modal__tab-count">{count}</span>
              </button>
            );
          })}
        </div>

        {/* 事件列表（可滚动） */}
        <div className="query-events-modal__body" ref={bodyRef}>
          <DiagnosticsEventList
            formatSourceLabel={formatSourceLabel}
            rows={filtered}
            timeKey={timeKey}
            title=""
            emptyText={emptyText}
          />
        </div>
      </div>
    </div>
  );
}


export function QueryEventsModal({ events = [], onClose }) {
  return (
    <RuntimeEventsModal
      events={events}
      formatSourceLabel={formatSourceModeLabel}
      onClose={onClose}
      resolveMode={(event) => event?.mode_type}
      timeKey="timestamp"
      title="查询事件日志"
    />
  );
}


export function PurchaseEventsModal({ events = [], onClose }) {
  return (
    <RuntimeEventsModal
      emptyText="暂无购买事件"
      events={events}
      onClose={onClose}
      resolveMode={(event) => event?.source_mode_type}
      timeKey="occurred_at"
      title="购买事件日志"
    />
  );
}
