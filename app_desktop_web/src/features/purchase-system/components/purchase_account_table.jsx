export function PurchaseAccountTable({ rows }) {
  return (
    <section className="purchase-account-table">
      <div className="purchase-account-table__title">账号统计</div>
      <table aria-label="购买账号统计" className="account-table">
        <thead>
          <tr>
            <th scope="col">账号</th>
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
                <td>{row.submitted_product_count ?? 0}</td>
                <td>{row.purchase_success_count ?? 0}</td>
                <td>{row.purchase_failed_count ?? 0}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td className="account-table__empty" colSpan={4}>暂无账号统计</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
