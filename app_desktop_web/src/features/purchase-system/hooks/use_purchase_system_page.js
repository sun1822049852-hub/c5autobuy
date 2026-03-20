import { useEffect, useState } from "react";


const EMPTY_STATUS = {
  running: false,
  message: "未运行",
  queue_size: 0,
  active_account_count: 0,
  total_account_count: 0,
  total_purchased_count: 0,
  active_query_config: null,
  matched_product_count: 0,
  purchase_success_count: 0,
  purchase_failed_count: 0,
  recent_events: [],
  accounts: [],
  item_rows: [],
};


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function normalizeStatus(status) {
  return {
    ...EMPTY_STATUS,
    ...status,
    recent_events: Array.isArray(status?.recent_events) ? status.recent_events : [],
    accounts: Array.isArray(status?.accounts)
      ? status.accounts.map((account) => ({
        ...account,
        account_id: String(account?.account_id ?? ""),
        purchase_disabled: Boolean(account?.purchase_disabled),
      }))
      : [],
    item_rows: Array.isArray(status?.item_rows) ? status.item_rows : [],
  };
}


function buildEnabledAccountIds(rows) {
  return Array.from(new Set((rows || [])
    .filter((row) => row?.account_id && !row.purchase_disabled)
    .map((row) => String(row.account_id))));
}


export function usePurchaseSystemPage({ client }) {
  const [status, setStatus] = useState(EMPTY_STATUS);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionPending, setIsActionPending] = useState(false);
  const [isSettingsPending, setIsSettingsPending] = useState(false);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [enabledAccountDraft, setEnabledAccountDraft] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;

    const refreshStatus = async ({ silent = false } = {}) => {
      if (!silent) {
        setIsLoading(true);
      }
      try {
        const nextStatus = await client.getPurchaseRuntimeStatus();
        if (!active) {
          return;
        }
        setStatus(normalizeStatus(nextStatus));
        setLoadError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setLoadError(toErrorMessage(error));
      } finally {
        if (active && !silent) {
          setIsLoading(false);
        }
      }
    };

    refreshStatus();
    const timerId = window.setInterval(() => {
      refreshStatus({ silent: true });
    }, 1500);

    return () => {
      active = false;
      window.clearInterval(timerId);
    };
  }, [client]);

  useEffect(() => {
    if (settingsDirty || isSettingsPending) {
      return;
    }

    setEnabledAccountDraft(buildEnabledAccountIds(status.accounts));
  }, [isSettingsPending, settingsDirty, status.accounts]);

  async function onRuntimeAction() {
    setIsActionPending(true);
    try {
      const nextStatus = status.running
        ? await client.stopPurchaseRuntime()
        : await client.startPurchaseRuntime();
      setStatus(normalizeStatus(nextStatus));
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsActionPending(false);
    }
  }

  function onTogglePurchaseAccount(accountId) {
    const nextAccountId = String(accountId);
    setSettingsDirty(true);
    setEnabledAccountDraft((current) => (
      current.includes(nextAccountId)
        ? current.filter((item) => item !== nextAccountId)
        : [...current, nextAccountId]
    ));
  }

  async function onSavePurchaseAccounts() {
    setIsSettingsPending(true);
    try {
      const enabledIds = new Set(enabledAccountDraft.map((item) => String(item)));
      const changedRows = status.accounts.filter((row) => (
        enabledIds.has(String(row.account_id)) === Boolean(row.purchase_disabled)
      ));

      await Promise.all(changedRows.map((row) => client.updateAccountPurchaseConfig(
        row.account_id,
        {
          purchase_disabled: !enabledIds.has(String(row.account_id)),
          selected_steam_id: row.selected_steam_id ?? null,
        },
      )));

      const nextStatus = await client.getPurchaseRuntimeStatus();
      setStatus(normalizeStatus(nextStatus));
      setSettingsDirty(false);
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsSettingsPending(false);
    }
  }

  return {
    accountRows: status.accounts,
    activeQueryConfig: status.active_query_config,
    actionLabel: status.running ? "停止扫货" : "开始扫货",
    isActionPending,
    isLoading,
    isSettingsPending,
    itemRows: status.item_rows,
    loadError,
    onRuntimeAction,
    onSavePurchaseAccounts,
    onTogglePurchaseAccount,
    queueSize: status.queue_size,
    recentEvents: status.recent_events,
    runtimeMessage: status.active_query_config?.message || status.message,
    settingsDirty,
    totalAccountCount: status.total_account_count,
    totalPurchasedCount: status.total_purchased_count,
    activeAccountCount: status.active_account_count,
    status,
    enabledAccountDraft,
  };
}
