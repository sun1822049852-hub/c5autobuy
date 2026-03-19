import { useEffect, useState } from "react";


const EMPTY_STATUS = {
  running: false,
  message: "未运行",
  active_query_config: null,
  matched_product_count: 0,
  purchase_success_count: 0,
  purchase_failed_count: 0,
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
    accounts: Array.isArray(status?.accounts) ? status.accounts : [],
    item_rows: Array.isArray(status?.item_rows) ? status.item_rows : [],
  };
}


export function usePurchaseSystemPage({ client }) {
  const [status, setStatus] = useState(EMPTY_STATUS);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionPending, setIsActionPending] = useState(false);
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

  return {
    accountRows: status.accounts,
    activeQueryConfig: status.active_query_config,
    actionLabel: status.running ? "停止扫货" : "开始扫货",
    isActionPending,
    isLoading,
    itemRows: status.item_rows,
    loadError,
    onRuntimeAction,
    runtimeMessage: status.active_query_config?.message || status.message,
    status,
  };
}
