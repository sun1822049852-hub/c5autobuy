import { useEffect, useState } from "react";


export function PurchaseConfigDrawer({
  account,
  detail,
  isLoading,
  open,
  onClose,
  onSubmit,
}) {
  const [selectedSteamId, setSelectedSteamId] = useState("");
  const [disabled, setDisabled] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    setSelectedSteamId(detail?.selected_steam_id ?? account?.selected_steam_id ?? "");
    setDisabled(Boolean(account?.disabled));
  }, [account, detail, open]);

  if (!open || !account) {
    return null;
  }

  return (
    <aside aria-label="购买配置" className="drawer-surface" role="complementary">
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          await onSubmit?.({
            disabled,
            selected_steam_id: selectedSteamId || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title">购买配置</h2>
            <p className="surface-subtitle">库存已满的仓库不可选，禁用后账号不再参与购买任务分配。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
        </div>

        <div className="drawer-stack">
          <div className="drawer-card">
            <div className="drawer-card__label">当前账号</div>
            <div className="drawer-card__value">{account.display_name || account.remark_name || account.account_id}</div>
          </div>

          {isLoading ? (
            <div className="drawer-note">正在加载仓库详情...</div>
          ) : (
            <>
              <label className="form-field">
                <span className="form-label">当前仓库</span>
                <select
                  className="form-select"
                  value={selectedSteamId}
                  onChange={(event) => setSelectedSteamId(event.target.value)}
                >
                  {(detail?.inventories ?? []).map((inventory) => (
                    <option
                      key={inventory.steamId}
                      disabled={!inventory.is_available}
                      value={inventory.steamId}
                    >
                      {inventory.is_available ? inventory.steamId : `${inventory.steamId}（库存已满）`}
                    </option>
                  ))}
                </select>
              </label>

              <label className="drawer-checkbox">
                <input
                  checked={disabled}
                  type="checkbox"
                  onChange={(event) => setDisabled(event.target.checked)}
                />
                <span>禁用该账号的购买能力</span>
              </label>

              {detail?.last_error ? (
                <div className="drawer-note drawer-note--warn">{detail.last_error}</div>
              ) : null}

              <div className="drawer-list">
                {(detail?.inventories ?? []).map((inventory) => (
                  <div key={inventory.steamId} className="drawer-inventory">
                    <div className="drawer-inventory__title">
                      {inventory.steamId}
                      {inventory.is_selected ? "（当前）" : ""}
                    </div>
                    <div className="drawer-inventory__meta">
                      库存 {inventory.inventory_num}/{inventory.inventory_max}，剩余容量 {inventory.remaining_capacity}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="surface-actions">
          <button className="accent-button" disabled={isLoading} type="submit">保存</button>
        </div>
      </form>
    </aside>
  );
}
