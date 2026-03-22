import {
  formatQuerySourceModeSummary,
} from "../stats/stats_shared.js";
import { StatsRangeControls } from "../stats/stats_range_controls.jsx";
import { useQueryStatsPage } from "./hooks/use_query_stats_page.js";


export function QueryStatsPage({ client }) {
  const {
    filters,
    isLoading,
    loadError,
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
        <div className="stats-toolbar__copy">
          <div className="stats-toolbar__eyebrow">Stats</div>
          <div className="stats-toolbar__title">查询统计</div>
          <div className="stats-toolbar__subtitle">按商品聚合命中、成功、失败与来源统计。</div>
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

      {loadError ? (
        <section className="query-system-page__error">{loadError}</section>
      ) : null}

      <section className="stats-table-panel">
        <table aria-label="查询统计表" className="stats-table">
          <thead>
            <tr>
              <th scope="col">商品</th>
              <th scope="col">查询次数</th>
              <th scope="col">命中</th>
              <th scope="col">成功</th>
              <th scope="col">失败</th>
              <th scope="col">来源</th>
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
                <td className="stats-table__empty" colSpan={6}>
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
