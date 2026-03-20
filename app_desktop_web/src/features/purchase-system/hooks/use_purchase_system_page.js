import { useEffect, useMemo, useState } from "react";


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
        display_name: account?.display_name ? String(account.display_name) : null,
        purchase_disabled: Boolean(account?.purchase_disabled),
        selected_inventory_name: account?.selected_inventory_name
          ? String(account.selected_inventory_name)
          : null,
      }))
      : [],
    item_rows: Array.isArray(status?.item_rows) ? status.item_rows : [],
  };
}


function normalizeConfigList(configs) {
  if (!Array.isArray(configs)) {
    return [];
  }

  return configs.map((config) => ({
    config_id: String(config?.config_id ?? ""),
    name: String(config?.name ?? ""),
    description: config?.description ? String(config.description) : "",
  })).filter((config) => config.config_id && config.name);
}


function getConfigById(configs, configId) {
  if (!configId) {
    return null;
  }

  return configs.find((config) => config.config_id === configId) || null;
}


export function usePurchaseSystemPage({ client }) {
  const [status, setStatus] = useState(EMPTY_STATUS);
  const [configList, setConfigList] = useState([]);
  const [selectedConfigId, setSelectedConfigId] = useState(null);
  const [selectorDraftId, setSelectorDraftId] = useState(null);
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
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

    const loadPage = async () => {
      setIsLoading(true);
      try {
        const [nextStatus, nextConfigs] = await Promise.all([
          client.getPurchaseRuntimeStatus(),
          client.listQueryConfigs(),
        ]);
        if (!active) {
          return;
        }
        setStatus(normalizeStatus(nextStatus));
        setConfigList(normalizeConfigList(nextConfigs));
        setLoadError("");
      } catch (error) {
        if (!active) {
          return;
        }
        setLoadError(toErrorMessage(error));
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    loadPage();
    const timerId = window.setInterval(() => {
      refreshStatus({ silent: true });
    }, 1500);

    return () => {
      active = false;
      window.clearInterval(timerId);
    };
  }, [client]);

  useEffect(() => {
    const activeConfigId = status.active_query_config?.config_id || null;
    if (activeConfigId) {
      setSelectedConfigId(activeConfigId);
      return;
    }

    if (selectedConfigId && !getConfigById(configList, selectedConfigId)) {
      setSelectedConfigId(null);
    }
  }, [configList, selectedConfigId, status.active_query_config]);

  const selectedConfig = useMemo(
    () => getConfigById(configList, selectedConfigId),
    [configList, selectedConfigId],
  );
  const activeConfig = status.active_query_config;
  const configDisplayName = activeConfig?.config_name || selectedConfig?.name || "未选择配置";
  const runtimeMessage = activeConfig?.message || status.message || "未运行";
  const isRuntimeRunning = Boolean(status.running);
  const actionLabel = isRuntimeRunning ? "停止扫货" : "开始扫货";
  const configActionLabel = isRuntimeRunning ? "切换配置" : "选择配置";
  const isActionDisabled = isActionPending || (!isRuntimeRunning && !selectedConfigId);
  const dialogActionLabel = isRuntimeRunning ? "切换到该配置" : "使用该配置";

  async function refreshConfigList() {
    const nextConfigs = await client.listQueryConfigs();
    const normalized = normalizeConfigList(nextConfigs);
    setConfigList(normalized);
    return normalized;
  }

  async function onRuntimeAction() {
    if (!isRuntimeRunning && !selectedConfigId) {
      return;
    }

    setIsActionPending(true);
    try {
      const nextStatus = isRuntimeRunning
        ? await client.stopPurchaseRuntime()
        : await client.startPurchaseRuntime(selectedConfigId);
      setStatus(normalizeStatus(nextStatus));
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsActionPending(false);
    }
  }

  async function openConfigDialog() {
    try {
      const nextConfigs = await refreshConfigList();
      const nextSelectionId = activeConfig?.config_id
        || selectedConfigId
        || nextConfigs[0]?.config_id
        || null;
      setSelectorDraftId(nextSelectionId);
      setIsConfigDialogOpen(true);
      setLoadError("");
    } catch (error) {
      setLoadError(toErrorMessage(error));
    }
  }

  function closeConfigDialog() {
    if (isActionPending) {
      return;
    }
    setIsConfigDialogOpen(false);
    setSelectorDraftId(null);
  }

  async function confirmConfigSelection() {
    if (!selectorDraftId) {
      return;
    }

    setSelectedConfigId(selectorDraftId);
    if (!isRuntimeRunning || selectorDraftId === activeConfig?.config_id) {
      setIsConfigDialogOpen(false);
      setSelectorDraftId(null);
      return;
    }

    setIsActionPending(true);
    try {
      const nextStatus = await client.startPurchaseRuntime(selectorDraftId);
      setStatus(normalizeStatus(nextStatus));
      setLoadError("");
      setIsConfigDialogOpen(false);
      setSelectorDraftId(null);
    } catch (error) {
      setLoadError(toErrorMessage(error));
    } finally {
      setIsActionPending(false);
    }
  }

  return {
    accountRows: status.accounts,
    actionLabel,
    configActionLabel,
    configDisplayName,
    configList,
    dialogActionLabel,
    activeQueryConfig: activeConfig,
    isActionDisabled,
    isActionPending,
    isConfigDialogOpen,
    isLoading,
    itemRows: status.item_rows,
    loadError,
    onConfigDialogSelect: setSelectorDraftId,
    onOpenConfigDialog: openConfigDialog,
    onCloseConfigDialog: closeConfigDialog,
    onConfirmConfigDialog: confirmConfigSelection,
    onRuntimeAction,
    queueSize: status.queue_size,
    recentEvents: status.recent_events,
    runtimeMessage,
    runtimeSessionId: status.runtime_session_id || null,
    selectedDialogConfigId: selectorDraftId,
    status,
    totalAccountCount: status.total_account_count,
    totalPurchasedCount: status.total_purchased_count,
    activeAccountCount: status.active_account_count,
  };
}
