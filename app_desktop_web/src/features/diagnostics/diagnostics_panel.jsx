import { useCallback, useRef, useState } from "react";

import { DiagnosticsSummary } from "./diagnostics_summary.jsx";
import { DiagnosticsTabs } from "./diagnostics_tabs.jsx";
import { LoginTaskDiagnosticsTab } from "./login_task_diagnostics_tab.jsx";
import { PurchaseDiagnosticsTab } from "./purchase_diagnostics_tab.jsx";
import { QueryDiagnosticsTab } from "./query_diagnostics_tab.jsx";
import { RuntimePageGuard } from "../shell/runtime_page_guard.jsx";


function renderTabBody(activeTab, snapshot) {
  if (activeTab === "purchase") {
    return <PurchaseDiagnosticsTab snapshot={snapshot.purchase} />;
  }
  if (activeTab === "login_tasks") {
    return <LoginTaskDiagnosticsTab snapshot={snapshot.login_tasks} />;
  }
  return <QueryDiagnosticsTab snapshot={snapshot.query} />;
}


export function DiagnosticsPanel({
  error,
  isLoading,
  isRefreshing,
  onRetryBootstrap = null,
  runtimeBootstrapError = "",
  runtimeBootstrapStatus = "ready",
  snapshot,
}) {
  const [activeTab, setActiveTab] = useState("query");
  const bodyRef = useRef(null);
  const handleTabSelect = useCallback((tabId) => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = 0;
    }
    setActiveTab(tabId);
  }, []);

  if (runtimeBootstrapStatus !== "ready") {
    return (
      <RuntimePageGuard
        description={runtimeBootstrapStatus === "error"
          ? "通用诊断运行时预热失败，请留在当前页重试。"
          : "首次进入通用诊断时，正在补齐诊断快照与运行态汇总。"}
        error={runtimeBootstrapStatus === "error" ? runtimeBootstrapError : ""}
        onRetry={runtimeBootstrapStatus === "error" ? onRetryBootstrap : null}
        title="正在加载通用诊断运行时"
      />
    );
  }

  return (
    <aside className="diagnostics-panel" aria-label="通用诊断面板">
      <header className="diagnostics-panel__header">
        <div>
          <div className="diagnostics-panel__eyebrow">运行诊断</div>
          <h2 className="diagnostics-panel__title">通用诊断面板</h2>
        </div>
        <div className="diagnostics-panel__status">
          {isLoading ? "加载中" : isRefreshing ? "刷新中" : "已连接"}
        </div>
      </header>

      {snapshot ? (
        <>
          <DiagnosticsSummary
            items={[
              { label: "查询状态", value: snapshot.summary.query_running ? "运行中" : "未运行" },
              { label: "购买状态", value: snapshot.summary.purchase_running ? "运行中" : "未运行" },
              { label: "当前配置", value: snapshot.summary.active_query_config_name || "无" },
              {
                label: "全局错误",
                value: snapshot.summary.last_error || "无",
                tone: snapshot.summary.last_error ? "danger" : "muted",
              },
            ]}
          />
          <DiagnosticsTabs activeTab={activeTab} onSelect={handleTabSelect} />
          <div className="diagnostics-panel__body" ref={bodyRef}>{renderTabBody(activeTab, snapshot)}</div>
        </>
      ) : (
        <div className="diagnostics-panel__empty">
          <div className="diagnostics-empty">{isLoading ? "正在加载诊断快照" : "诊断数据暂不可用"}</div>
        </div>
      )}

      {error ? <div className="diagnostics-panel__error">{error}</div> : null}
    </aside>
  );
}
