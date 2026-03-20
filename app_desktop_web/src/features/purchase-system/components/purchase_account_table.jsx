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
      <div className="purchase-account-table__title">账号统计</div>
      <table aria-label="购买账号统计" className="account-table">
        <thead>
          <tr>
            <th scope="col">账号</th>
            <th scope="col">池状态</th>
            <th scope="col">仓库占用</th>
            <th scope="col">提交件数</th>
            <th scope="col">成功件数</th>
            <th scope="col">失败件数</th>
          </tr>
        </thead>
        <tbody>
          {(rows || []).length ? (
            rows.map((row) => (
              <tr key={row.account_id}>
                <td>{row.display_name || row.account_id}</td>
                <td>{formatPoolState(row)}</td>
                <td>{formatInventoryUsage(row)}</td>
                <td>{row.submitted_product_count ?? 0}</td>
                <td>{row.purchase_success_count ?? 0}</td>
                <td>{row.purchase_failed_count ?? 0}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td className="account-table__empty" colSpan={6}>暂无账号统计</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
