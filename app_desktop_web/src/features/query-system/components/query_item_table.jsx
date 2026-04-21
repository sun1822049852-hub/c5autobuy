import { QueryItemRow } from "./query_item_row.jsx";


export function QueryItemTable({
  canManageItems,
  isDeleteMode,
  items,
  readOnly = false,
  onDeleteItem,
  onEditItem,
  onToggleManualPause,
  onOpenCreateItemDialog,
  onToggleDeleteMode,
}) {
  return (
    <section className="query-item-table" role="region" aria-label="商品配置列表">
      <div className="query-item-table__header">
        <div className="query-item-table__column-grid">
          <div className="query-item-table__column query-item-table__column--name">商品名</div>
          <div className="query-item-table__column">市场价</div>
          <div className="query-item-table__column">扫货价</div>
          <div className="query-item-table__column">磨损</div>
          <div className="query-item-table__column">new_api</div>
          <div className="query-item-table__column">fast_api</div>
          <div className="query-item-table__column">token</div>
        </div>

        <div className="query-item-table__toolbar">
          <button
            className="query-item-table__icon-button query-item-table__icon-button--create"
            type="button"
            aria-label="添加商品"
            disabled={!canManageItems}
            onClick={onOpenCreateItemDialog}
          >
            +
          </button>
          <button
            className={`query-item-table__icon-button query-item-table__icon-button--delete${isDeleteMode ? " is-active" : ""}`}
            type="button"
            aria-label="切换商品删除模式"
            disabled={!canManageItems}
            onClick={onToggleDeleteMode}
          >
            -
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="query-item-table__empty">
          {canManageItems ? "当前配置还没有商品，先从右上角 + 添加一件。" : "先从左侧选择一份配置。"}
        </div>
      ) : (
        <div className="query-item-table__list">
          {items.map((item) => (
            <QueryItemRow
              key={item.query_item_id}
              isDeleteMode={isDeleteMode}
              item={item}
              readOnly={readOnly}
              onDeleteItem={onDeleteItem}
              onEditItem={onEditItem}
              onToggleManualPause={onToggleManualPause}
            />
          ))}
        </div>
      )}
    </section>
  );
}
