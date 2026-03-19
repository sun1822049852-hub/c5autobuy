import { QueryItemRow } from "./query_item_row.jsx";


export function QueryItemTable({
  items,
  onEditItem,
}) {
  return (
    <section className="query-item-table" role="region" aria-label="商品列表">
      <div className="query-item-table__header">
        <div className="query-item-table__title">商品列表</div>
        <div className="query-item-table__subtitle">每行直接显示价格、磨损、目标分配数与模式状态。</div>
      </div>

      {items.length === 0 ? (
        <div className="query-item-table__empty">当前配置还没有商品，先从右上角添加一件。</div>
      ) : (
        <div className="query-item-table__list">
          {items.map((item) => (
            <QueryItemRow
              key={item.query_item_id}
              item={item}
              onEditItem={onEditItem}
            />
          ))}
        </div>
      )}
    </section>
  );
}
