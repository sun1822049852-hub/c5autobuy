function formatCapabilityState(row) {
  if (row.purchase_disabled) {
    return "已禁用购买";
  }
  if (row.purchase_capability_state === "bound") {
    return "已绑定";
  }
  if (row.purchase_capability_state === "expired") {
    return "登录失效";
  }
  if (row.purchase_capability_state === "unbound") {
    return "未绑定";
  }
  return row.purchase_capability_state || "--";
}


function formatPoolState(row) {
  if (row.purchase_disabled) {
    return "已禁用";
  }
  if (row.purchase_pool_state === "active") {
    return "活跃";
  }
  if (row.purchase_pool_state === "paused_no_inventory") {
    return "无仓库";
  }
  if (row.purchase_pool_state) {
    return row.purchase_pool_state;
  }
  return "--";
}


function formatInventoryName(row) {
  return row.selected_inventory_name || row.selected_steam_id || "未选择";
}


function formatInventoryUsage(row) {
  const maxValue = typeof row.selected_inventory_max === "number" ? row.selected_inventory_max : null;
  const remainingValue = typeof row.selected_inventory_remaining_capacity === "number"
    ? row.selected_inventory_remaining_capacity
    : null;

  if (maxValue == null || remainingValue == null) {
    return "--/--";
  }

  return `${Math.max(maxValue - remainingValue, 0)}/${maxValue}`;
}


export function PurchaseAccountTable({ rows }) {
  return (
    <section className="purchase-account-table">
      <div className="purchase-account-table__title">账号监控</div>
      <div className="purchase-account-table__subtitle">运行中只展示已绑定购买能力的账号状态、仓库与件数回执。</div>
      <table aria-label="购买账号监控" className="account-table">
        <thead>
          <tr>
            <th scope="col">账号</th>
            <th scope="col">购买状态</th>
            <th scope="col">池状态</th>
            <th scope="col">当前仓库</th>
            <th scope="col">仓库占用</th>
            <th scope="col">提交</th>
            <th scope="col">成功</th>
            <th scope="col">失败</th>
            <th scope="col">已购</th>
          </tr>
        </thead>
        <tbody>
          {(rows || []).length ? (
            rows.map((row) => (
              <tr key={row.account_id}>
                <td>
                  <div className="purchase-account-table__account-name">{row.display_name || row.account_id}</div>
                  {row.last_error ? (
                    <div className="purchase-account-table__account-error">{row.last_error}</div>
                  ) : null}
                </td>
                <td>{formatCapabilityState(row)}</td>
                <td>{formatPoolState(row)}</td>
                <td>{formatInventoryName(row)}</td>
                <td>{formatInventoryUsage(row)}</td>
                <td>{row.submitted_product_count ?? 0}</td>
                <td>{row.purchase_success_count ?? 0}</td>
                <td>{row.purchase_failed_count ?? 0}</td>
                <td>{row.total_purchased_count ?? 0}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td className="account-table__empty" colSpan={9}>暂无账号统计</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
