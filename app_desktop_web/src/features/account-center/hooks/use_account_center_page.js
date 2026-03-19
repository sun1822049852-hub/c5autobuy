import { useEffect, useMemo, useRef, useState } from "react";

import { useLoginTaskStream } from "./use_login_task_stream.js";
import { createUiStateStore } from "../state/ui_state_store.js";


const PAGE_STORE = createUiStateStore("account-center-page");
const DEFAULT_UI_STATE = {
  activeFilter: "all",
  searchTerm: "",
};


function getDisplayName(row) {
  return row.display_name || row.remark_name || row.c5_nick_name || row.default_name || row.account_id;
}


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function buildProxyDisplay(proxyMode, proxyUrl) {
  if (proxyMode === "direct") {
    return "直连";
  }

  return proxyUrl || "未配置代理";
}


function isNotLoggedIn(row) {
  return row.purchase_status_code === "not_logged_in";
}


function hasNoApiKey(row) {
  return !row.api_key_present;
}


function isPurchasable(row) {
  return row.purchase_status_code === "selected_warehouse" || row.purchase_status_code === "purchasable";
}


function matchesFilter(row, activeFilter) {
  if (activeFilter === "not_logged_in") {
    return isNotLoggedIn(row);
  }

  if (activeFilter === "missing_api_key") {
    return hasNoApiKey(row);
  }

  if (activeFilter === "purchasable") {
    return isPurchasable(row);
  }

  return true;
}


function matchesSearch(row, keyword) {
  if (!keyword) {
    return true;
  }

  const haystack = [
    row.display_name,
    row.remark_name,
    row.c5_nick_name,
    row.default_name,
    row.purchase_status_text,
    row.proxy_display,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return haystack.includes(keyword.toLowerCase());
}


function buildOverviewCards(rows) {
  return [
    {
      id: "all",
      label: "总账号",
      value: rows.length,
      hint: "全部可见账号",
    },
    {
      id: "not_logged_in",
      label: "未登录",
      value: rows.filter(isNotLoggedIn).length,
      hint: "优先处理登录问题",
    },
    {
      id: "missing_api_key",
      label: "无 API Key",
      value: rows.filter(hasNoApiKey).length,
      hint: "需要补录或更新 key",
    },
    {
      id: "purchasable",
      label: "可购买",
      value: rows.filter(isPurchasable).length,
      hint: "当前已绑定可用仓库",
    },
  ];
}


function buildAccountUpdatePayload(account, partialPayload) {
  const hasApiKey = Object.prototype.hasOwnProperty.call(partialPayload, "api_key");
  const hasProxyUrl = Object.prototype.hasOwnProperty.call(partialPayload, "proxy_url");

  return {
    remark_name: Object.prototype.hasOwnProperty.call(partialPayload, "remark_name")
      ? partialPayload.remark_name
      : account.remark_name ?? null,
    proxy_mode: partialPayload.proxy_mode ?? account.proxy_mode ?? "direct",
    proxy_url: hasProxyUrl ? partialPayload.proxy_url : account.proxy_url ?? null,
    api_key: hasApiKey ? partialPayload.api_key : account.api_key ?? null,
  };
}


function buildLoginDrawerAccount(account) {
  return {
    ...account,
    display_name: getDisplayName(account),
    proxy_display: account.proxy_display || buildProxyDisplay(account.proxy_mode, account.proxy_url),
  };
}


function buildLoginTaskStatusText(account, taskSnapshot) {
  const displayName = getDisplayName(account);

  if (taskSnapshot.state === "succeeded") {
    return `登录任务已完成：${displayName}`;
  }

  if (taskSnapshot.state === "failed") {
    return `登录任务失败：${displayName}`;
  }

  if (taskSnapshot.state === "cancelled") {
    return `登录任务已取消：${displayName}`;
  }

  if (taskSnapshot.state === "conflict") {
    return `登录任务冲突：${displayName}`;
  }

  if (taskSnapshot.state === "running") {
    return `登录任务进行中：${displayName}`;
  }

  return `登录任务已创建：${displayName}`;
}


function getLatestTaskMessage(taskSnapshot) {
  return taskSnapshot.events?.[taskSnapshot.events.length - 1]?.message || taskSnapshot.error || "";
}


export function useAccountCenterPage({ client }) {
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [uiState, setUiState] = useState(() => ({
    ...DEFAULT_UI_STATE,
    ...PAGE_STORE.read(DEFAULT_UI_STATE),
  }));
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [remarkDialogAccount, setRemarkDialogAccount] = useState(null);
  const [apiKeyDialogAccount, setApiKeyDialogAccount] = useState(null);
  const [proxyDialogAccount, setProxyDialogAccount] = useState(null);
  const [purchaseDrawerState, setPurchaseDrawerState] = useState({
    account: null,
    detail: null,
    isLoading: false,
    isRefreshing: false,
    open: false,
  });
  const [loginDrawerAccount, setLoginDrawerAccount] = useState(null);
  const loginDrawerAccountRef = useRef(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [recentLoginTask, setRecentLoginTask] = useState("等待接入真实任务流");
  const [recentError, setRecentError] = useState("当前无错误记录");
  const [recentModification, setRecentModification] = useState("尚未发生配置改动");
  const loginTaskStream = useLoginTaskStream({ client });

  useEffect(() => {
    let isMounted = true;

    async function loadInitialAccounts() {
      setIsLoading(true);
      setLoadError("");

      try {
        const nextRows = await client.listAccountCenterAccounts();
        if (!isMounted) {
          return;
        }

        setRows(nextRows);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message = toErrorMessage(error);
        setLoadError(message);
        setRecentError(`加载账号失败：${message}`);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadInitialAccounts();

    return () => {
      isMounted = false;
    };
  }, [client]);

  useEffect(() => {
    PAGE_STORE.write(uiState);
  }, [uiState]);

  useEffect(() => {
    loginDrawerAccountRef.current = loginDrawerAccount;
  }, [loginDrawerAccount]);

  const overviewCards = useMemo(() => buildOverviewCards(rows), [rows]);
  const filteredRows = useMemo(() => rows.filter((row) => (
    matchesFilter(row, uiState.activeFilter) && matchesSearch(row, uiState.searchTerm)
  )), [rows, uiState.activeFilter, uiState.searchTerm]);

  async function refreshAccounts() {
    setIsLoading(true);
    setLoadError("");

    try {
      const nextRows = await client.listAccountCenterAccounts();
      setRows(nextRows);
      return nextRows;
    } catch (error) {
      const message = toErrorMessage(error);
      setLoadError(message);
      setRecentError(`加载账号失败：${message}`);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAction(action, successMessageBuilder) {
    try {
      const result = await action();
      setRecentError("当前无错误记录");
      const nextMessage = typeof successMessageBuilder === "function"
        ? successMessageBuilder(result)
        : successMessageBuilder;
      if (nextMessage) {
        setRecentModification(nextMessage);
      }
      return result;
    } catch (error) {
      setRecentError(toErrorMessage(error));
      return null;
    }
  }

  async function runLoginForAccount(account) {
    const loginAccount = buildLoginDrawerAccount(account);
    setLoginDrawerAccount(loginAccount);

    try {
      return await loginTaskStream.start(loginAccount.account_id, {
        async onSnapshot(snapshot) {
          setRecentLoginTask(buildLoginTaskStatusText(loginAccount, snapshot));

          if (snapshot.state === "failed") {
            setRecentError(`登录失败：${getLatestTaskMessage(snapshot) || "未知错误"}`);
          }
        },
        async onTerminal(snapshot) {
          if (snapshot.state === "succeeded") {
            const nextRows = await refreshAccounts();
            const nextAccount = nextRows.find((row) => row.account_id === loginAccount.account_id);
            if (nextAccount && loginDrawerAccountRef.current?.account_id === loginAccount.account_id) {
              setLoginDrawerAccount(buildLoginDrawerAccount(nextAccount));
            }
          }
        },
      });
    } catch (error) {
      setRecentError(`发起登录失败：${toErrorMessage(error)}`);
      return null;
    }
  }

  return {
    activeFilter: uiState.activeFilter,
    apiKeyDialogAccount,
    closeApiKeyDialog() {
      setApiKeyDialogAccount(null);
    },
    closeContextMenu() {
      setContextMenu(null);
    },
    closeCreateDialog() {
      setCreateDialogOpen(false);
    },
    closeLoginDrawer() {
      setLoginDrawerAccount(null);
      loginTaskStream.reset();
    },
    closeProxyDialog() {
      setProxyDialogAccount(null);
    },
    closePurchaseDrawer() {
      setPurchaseDrawerState({
        account: null,
        detail: null,
        isLoading: false,
        isRefreshing: false,
        open: false,
      });
    },
    closeRemarkDialog() {
      setRemarkDialogAccount(null);
    },
    contextMenu,
    createDialogOpen,
    deleteAccount: async (account) => {
      setContextMenu(null);

      const confirmed = typeof globalThis.window?.confirm === "function"
        ? globalThis.window.confirm(`确认删除账号“${getDisplayName(account)}”吗？`)
        : true;

      if (!confirmed) {
        return;
      }

      await handleAction(async () => {
        await client.deleteAccount(account.account_id);
        await refreshAccounts();
      }, `已删除账号：${getDisplayName(account)}`);
    },
    filteredRows,
    isLoading,
    loadError,
    loginDrawerAccount,
    loginTaskSnapshot: loginTaskStream.taskSnapshot,
    isLoginTaskStarting: loginTaskStream.isStarting,
    openApiKeyDialog(account) {
      setApiKeyDialogAccount(account);
      setContextMenu(null);
    },
    openContextMenu(account, position) {
      setContextMenu({
        account,
        position,
      });
    },
    openCreateDialog() {
      setCreateDialogOpen(true);
      setContextMenu(null);
    },
    openNicknameDialog(account) {
      setRemarkDialogAccount(account);
      setContextMenu(null);
    },
    openProxyDialog(account) {
      setProxyDialogAccount(account);
      setContextMenu(null);
    },
    openPurchaseStatus: async (account) => {
      setContextMenu(null);

      if (isNotLoggedIn(account)) {
        setLoginDrawerAccount(buildLoginDrawerAccount(account));
        setRecentLoginTask(`待为${getDisplayName(account)}发起登录`);
        return;
      }

      setPurchaseDrawerState({
        account,
        detail: null,
        isLoading: true,
        isRefreshing: false,
        open: true,
      });

      try {
        const detail = await client.getPurchaseRuntimeInventoryDetail(account.account_id);
        setPurchaseDrawerState({
          account,
          detail,
          isLoading: false,
          isRefreshing: false,
          open: true,
        });
      } catch (error) {
        setPurchaseDrawerState({
          account: null,
          detail: null,
          isLoading: false,
          isRefreshing: false,
          open: false,
        });
        setRecentError(`加载购买配置失败：${toErrorMessage(error)}`);
      }
    },
    overviewCards,
    proxyDialogAccount,
    purchaseDrawerState,
    recentError,
    recentLoginTask,
    recentModification,
    refreshAccounts,
    remarkDialogAccount,
    searchTerm: uiState.searchTerm,
    setActiveFilter(nextFilter) {
      setUiState((current) => ({
        ...current,
        activeFilter: current.activeFilter === nextFilter && nextFilter !== "all" ? "all" : nextFilter,
      }));
    },
    setSearchTerm(nextSearchTerm) {
      setUiState((current) => ({
        ...current,
        searchTerm: nextSearchTerm,
      }));
    },
    submitApiKey: async (payload) => {
      const account = apiKeyDialogAccount;
      if (!account) {
        return null;
      }

      return handleAction(async () => {
        await client.updateAccount(account.account_id, buildAccountUpdatePayload(account, {
          api_key: payload.api_key,
        }));
        setApiKeyDialogAccount(null);
        await refreshAccounts();
      }, `已更新 API Key：${getDisplayName(account)}`);
    },
    submitCreate: async (payload, { startLoginAfterCreate = false } = {}) => {
      const outcome = await handleAction(async () => {
        const createdAccount = await client.createAccount(payload);
        setCreateDialogOpen(false);
        const nextRows = await refreshAccounts();
        return {
          createdAccount,
          nextRows,
        };
      }, ({ createdAccount }) => `已添加账号：${getDisplayName(createdAccount)}`);

      if (!outcome) {
        return null;
      }

      if (startLoginAfterCreate) {
        const nextAccount = outcome.nextRows.find((row) => row.account_id === outcome.createdAccount.account_id)
          ?? outcome.createdAccount;
        await runLoginForAccount(nextAccount);
      }

      return outcome.createdAccount;
    },
    submitProxy: async (payload) => {
      const account = proxyDialogAccount;
      if (!account) {
        return null;
      }

      const proxyChanged = account.proxy_mode !== payload.proxy_mode
        || (account.proxy_url ?? "") !== (payload.proxy_url ?? "");

      return handleAction(async () => {
        await client.updateAccount(account.account_id, buildAccountUpdatePayload(account, payload));
        setProxyDialogAccount(null);
        const nextRows = await refreshAccounts();
        const nextAccount = nextRows.find((row) => row.account_id === account.account_id);

        if (proxyChanged) {
          setLoginDrawerAccount(buildLoginDrawerAccount(nextAccount ?? {
            ...account,
            ...payload,
            proxy_display: buildProxyDisplay(payload.proxy_mode, payload.proxy_url),
          }));
          setRecentLoginTask(`待为${getDisplayName(nextAccount ?? account)}重新登录`);
        }
      }, `已更新代理：${getDisplayName(account)}`);
    },
    submitPurchaseConfig: async (payload) => {
      const account = purchaseDrawerState.account;
      if (!account) {
        return null;
      }

      return handleAction(async () => {
        await client.updateAccountPurchaseConfig(account.account_id, payload);
        setPurchaseDrawerState({
          account: null,
          detail: null,
          isLoading: false,
          isRefreshing: false,
          open: false,
        });
        await refreshAccounts();
      }, `已更新购买配置：${getDisplayName(account)}`);
    },
    refreshPurchaseConfigInventory: async () => {
      const account = purchaseDrawerState.account;
      if (!account) {
        return null;
      }

      setPurchaseDrawerState((current) => ({
        ...current,
        isRefreshing: true,
      }));

      try {
        const detail = await client.refreshPurchaseRuntimeInventoryDetail(account.account_id);
        setPurchaseDrawerState((current) => ({
          ...current,
          account,
          detail,
          isLoading: false,
          isRefreshing: false,
          open: true,
        }));
        setRecentError("当前无错误记录");
        setRecentModification(`已刷新仓库：${getDisplayName(account)}`);
        return detail;
      } catch (error) {
        setPurchaseDrawerState((current) => ({
          ...current,
          isRefreshing: false,
        }));
        setRecentError(`刷新仓库失败：${toErrorMessage(error)}`);
        return null;
      }
    },
    submitRemark: async (payload) => {
      const account = remarkDialogAccount;
      if (!account) {
        return null;
      }

      return handleAction(async () => {
        await client.updateAccount(account.account_id, buildAccountUpdatePayload(account, {
          remark_name: payload.remark_name,
        }));
        setRemarkDialogAccount(null);
        await refreshAccounts();
      }, `已更新备注：${payload.remark_name || getDisplayName(account)}`);
    },
    startLoginFromDrawer: async () => {
      const account = loginDrawerAccount;
      if (!account) {
        return null;
      }

      return runLoginForAccount(account);
    },
  };
}
