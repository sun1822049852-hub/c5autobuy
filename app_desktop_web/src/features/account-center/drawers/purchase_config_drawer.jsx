import { useEffect, useState } from "react";


function resolveRemainingSeconds(detail) {
  if (typeof detail?.auto_refresh_remaining_seconds === "number") {
    return Math.max(Math.floor(detail.auto_refresh_remaining_seconds), 0);
  }

  if (!detail?.auto_refresh_due_at) {
    return null;
  }

  const dueAtMs = Date.parse(detail.auto_refresh_due_at);
  if (Number.isNaN(dueAtMs)) {
    return null;
  }

  return Math.max(Math.floor((dueAtMs - Date.now()) / 1000), 0);
}


function formatRemainingSeconds(value) {
  if (value == null) {
    return "未计划";
  }

  const totalSeconds = Math.max(Math.floor(value), 0);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function getInventoryDisplayName(inventory) {
  if (!inventory) {
    return "";
  }

  return inventory.nickname || inventory.steamId || "";
}


export function PurchaseConfigDrawer({
  account,
  detail,
  isLoading,
  isRefreshing,
  open,
  onClose,
  onRefresh,
  onSubmit,
}) {
  const [selectedSteamId, setSelectedSteamId] = useState("");
  const [purchaseDisabled, setPurchaseDisabled] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    setSelectedSteamId(detail?.selected_steam_id ?? account?.selected_steam_id ?? "");
    setPurchaseDisabled(Boolean(account?.purchase_disabled));
  }, [account, detail, open]);

  useEffect(() => {
    if (!open) {
      setRemainingSeconds(null);
      return;
    }

    setRemainingSeconds(resolveRemainingSeconds(detail));
  }, [detail, open]);

  useEffect(() => {
    if (!open || remainingSeconds == null || remainingSeconds <= 0) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setRemainingSeconds((current) => {
        if (current == null || current <= 0) {
          return 0;
        }

        return current - 1;
      });
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [open, remainingSeconds]);

  if (!open || !account) {
    return null;
  }

  const currentInventory = (detail?.inventories ?? []).find((inventory) => inventory.steamId === selectedSteamId)
    ?? (detail?.inventories ?? []).find((inventory) => inventory.is_selected)
    ?? null;
  const currentInventoryName = getInventoryDisplayName(currentInventory);

  return (
    <aside aria-label="购买配置" className="drawer-surface" role="complementary">
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          await onSubmit?.({
            purchase_disabled: purchaseDisabled,
            selected_steam_id: selectedSteamId || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title">购买配置</h2>
            <p className="surface-subtitle">库存已满的仓库不可选，禁用后账号会立刻移出购买池，但不会影响查询能力。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
        </div>

        <div className="drawer-stack">
          <div className="drawer-card">
            <div className="drawer-card__label">当前账号</div>
            <div className="drawer-card__value">{account.display_name || account.remark_name || account.account_id}</div>
          </div>

          <div className="drawer-card">
            <div className="drawer-card__label">当前仓库</div>
            <div className="drawer-card__value">{currentInventoryName || "未选择仓库"}</div>
            <div className="drawer-card__value">
              当前仓库占用 {currentInventory
                ? `${currentInventory.inventory_num}/${currentInventory.inventory_max}`
                : "--/--"}
            </div>
            <div className="drawer-card__label">自动刷新剩余时间 {formatRemainingSeconds(remainingSeconds)}</div>
          </div>

          {isLoading ? (
            <div className="drawer-note">正在加载仓库详情...</div>
          ) : (
            <>
              <div className="surface-actions">
                <button
                  className="ghost-button"
                  disabled={isRefreshing}
                  type="button"
                  onClick={() => onRefresh?.()}
                >
                  {isRefreshing ? "刷新中..." : "手动刷新仓库"}
                </button>
              </div>

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
                      {inventory.is_available
                        ? getInventoryDisplayName(inventory)
                        : `${getInventoryDisplayName(inventory)}（库存已满）`}
                    </option>
                  ))}
                </select>
              </label>

              <label className="drawer-checkbox">
                <input
                  checked={purchaseDisabled}
                  type="checkbox"
                  onChange={(event) => setPurchaseDisabled(event.target.checked)}
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
                      {getInventoryDisplayName(inventory)}
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
          <button className="accent-button" disabled={isLoading || isRefreshing} type="submit">保存</button>
        </div>
      </form>
    </aside>
  );
}
