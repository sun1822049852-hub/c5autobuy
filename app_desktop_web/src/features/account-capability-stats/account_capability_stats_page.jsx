import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";
import { ErrorNotice } from "../../shared/error_notice.jsx";
import { RuntimePageGuard } from "../shell/runtime_page_guard.jsx";
import { StatsRangeControls } from "../stats/stats_range_controls.jsx";
import { useAccountCapabilityStatsPage } from "./hooks/use_account_capability_stats_page.js";


function AccountCapabilityStatsPageContent({ client }) {
  const {
    filters,
    isLoading,
    loadError,
    onDismissError,
    onDateChange,
    onEndDateChange,
    onRangeModeChange,
    onRefresh,
    onStartDateChange,
    rows,
  } = useAccountCapabilityStatsPage({ client });

  return (
    <section className="stats-page stats-page--compact" aria-label="账号能力统计">
      <section className="stats-toolbar">
        <div className="stats-toolbar__copy" style={NO_SELECT_STYLE}>
          <div className="stats-toolbar__eyebrow">Stats</div>
          <div className="stats-toolbar__title">账号能力统计</div>
          <div className="stats-toolbar__subtitle">聚合三类查询器与购买链路的延迟表现。</div>
        </div>

        <div className="stats-toolbar__controls">
          <StatsRangeControls
            filters={filters}
            onDateChange={onDateChange}
            onEndDateChange={onEndDateChange}
            onRangeModeChange={onRangeModeChange}
            onRefresh={onRefresh}
            onStartDateChange={onStartDateChange}
          />
        </div>
      </section>

      <ErrorNotice message={loadError} onClose={onDismissError} />

      <section className="stats-table-panel">
        <table aria-label="账号能力统计表" className="stats-table stats-table--compact-head">
          <thead>
            <tr>
              <th scope="col" style={NO_SELECT_STYLE}>账号</th>
              <th scope="col" style={NO_SELECT_STYLE}>api查询器</th>
              <th scope="col" style={NO_SELECT_STYLE}>api高速查询器</th>
              <th scope="col" style={NO_SELECT_STYLE}>浏览器查询器</th>
              <th scope="col" style={NO_SELECT_STYLE}>发单速度</th>
              <th scope="col" style={NO_SELECT_STYLE}>购买速度</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr key={row.account_id}>
                <td>{row.account_display_name}</td>
                <td>{row.new_api.display_text}</td>
                <td>{row.fast_api.display_text}</td>
                <td>{row.browser.display_text}</td>
                <td>{row.create_order.display_text}</td>
                <td>{row.submit_order.display_text}</td>
              </tr>
            )) : (
              <tr>
                <td className="stats-table__empty" colSpan={6} style={NO_SELECT_STYLE}>
                  {isLoading ? "统计加载中..." : "暂无统计数据"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </section>
  );
}

export function AccountCapabilityStatsPage({
  client,
  onRetryBootstrap = null,
  runtimeBootstrapError = "",
  runtimeBootstrapStatus = "ready",
}) {
  if (runtimeBootstrapStatus !== "ready") {
    return (
      <RuntimePageGuard
        description={runtimeBootstrapStatus === "error"
          ? "账号能力统计运行时预热失败，请留在当前页重试。"
          : "首次进入账号能力统计时，正在补齐统计快照与运行态汇总。"}
        error={runtimeBootstrapStatus === "error" ? runtimeBootstrapError : ""}
        onRetry={runtimeBootstrapStatus === "error" ? onRetryBootstrap : null}
        title="正在加载账号能力统计运行时"
      />
    );
  }

  return <AccountCapabilityStatsPageContent client={client} />;
}
