import { NO_SELECT_STYLE } from "../../shared/no_select_style.js";
import { ErrorNotice } from "../../shared/error_notice.jsx";
import { RuntimePageGuard } from "../shell/runtime_page_guard.jsx";
import {
  formatQuerySourceModeSummary,
} from "../stats/stats_shared.js";
import { StatsRangeControls } from "../stats/stats_range_controls.jsx";
import { useQueryStatsPage } from "./hooks/use_query_stats_page.js";


function QueryStatsPageContent({ client }) {
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
  } = useQueryStatsPage({ client });

  return (
    <section className="stats-page stats-page--compact" aria-label="查询统计">
      <section className="stats-toolbar">
        <div className="stats-toolbar__copy" style={NO_SELECT_STYLE}>
          <div className="stats-toolbar__eyebrow">Stats</div>
          <div className="stats-toolbar__title">查询统计</div>
          <div className="stats-toolbar__subtitle">按商品聚合命中、成功、下单失败件数与来源统计。</div>
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

      <ErrorNotice
        details={loadError?.details || []}
        message={loadError?.message || ""}
        onClose={onDismissError}
      />

      <section className="stats-table-panel">
        <table aria-label="查询统计表" className="stats-table">
          <thead>
            <tr>
              <th scope="col" style={NO_SELECT_STYLE}>商品</th>
              <th scope="col" style={NO_SELECT_STYLE}>查询次数</th>
              <th scope="col" style={NO_SELECT_STYLE}>命中</th>
              <th scope="col" style={NO_SELECT_STYLE}>成功</th>
              <th scope="col" style={NO_SELECT_STYLE}>下单失败件数</th>
              <th scope="col" style={NO_SELECT_STYLE}>来源</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row) => (
              <tr key={row.external_item_id}>
                <td>{row.item_name}</td>
                <td>{row.query_execution_count}</td>
                <td>{row.matched_product_count}</td>
                <td>{row.purchase_success_count}</td>
                <td>{row.purchase_failed_count}</td>
                <td>{formatQuerySourceModeSummary(row.source_mode_stats)}</td>
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

export function QueryStatsPage({
  client,
  onRetryBootstrap = null,
  runtimeBootstrapError = "",
  runtimeBootstrapStatus = "ready",
}) {
  if (runtimeBootstrapStatus !== "ready") {
    return (
      <RuntimePageGuard
        description={runtimeBootstrapStatus === "error"
          ? "查询统计运行时预热失败，请留在当前页重试。"
          : "首次进入查询统计时，正在补齐统计快照与运行态汇总。"}
        error={runtimeBootstrapStatus === "error" ? runtimeBootstrapError : ""}
        onRetry={runtimeBootstrapStatus === "error" ? onRetryBootstrap : null}
        title="正在加载查询统计运行时"
      />
    );
  }

  return <QueryStatsPageContent client={client} />;
}
