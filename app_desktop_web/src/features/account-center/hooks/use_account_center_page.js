import { useEffect, useMemo, useRef, useState } from "react";

import { useFloatingRuntimeModalState } from "../../purchase-system/hooks/use_floating_runtime_modal_state.js";
import { useLoginTaskStream } from "./use_login_task_stream.js";
import { createUiStateStore } from "../state/ui_state_store.js";


const PAGE_STORE = createUiStateStore("account-center-page");
const DEFAULT_UI_STATE = {
  activeFilter: "all",
  searchTerm: "",
};
const INITIAL_LOG_ENTRIES = [
  {
    id: "log-login-default",
    title: "最近登录任务",
    message: "等待接入真实任务流",
    meta: "登录抽屉与任务轮询会持续沉淀到这里。",
  },
  {
    id: "log-error-default",
    title: "最近错误",
    message: "当前无错误记录",
    meta: "请求失败、保存失败和冲突提示会沉到这里。",
  },
  {
    id: "log-modification-default",
    title: "最近修改",
    message: "尚未发生配置改动",
    meta: "备注、API Key、代理和购买配置改动都会留痕。",
  },
];
const QUERY_STATUS_ENABLED = "enabled";
const QUERY_STATUS_DISABLED = "disabled";
const QUERY_REASON_TEXTS = {
  ip_invalid: "IP 不在白名单内，请手动绑定",
  manual_disabled: "手动禁用",
  missing_api_key: "未配置",
  not_logged_in: "未登录",
};


function getDisplayName(row) {
  return row.display_name || row.remark_name || row.c5_nick_name || row.default_name || row.account_id;
}


function toErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}


function buildProxyDisplay(proxyMode, proxyUrl, publicIp = null) {
  if (proxyMode === "direct") {
    return publicIp || "未获取IP";
  }

  return proxyUrl || publicIp || "未配置代理";
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
    row.browser_proxy_display,
    row.api_proxy_display,
    row.api_public_ip,
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


function createLogEntry({ title, message, meta = "" }) {
  return {
    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    message,
    meta,
    title,
  };
}


function buildAccountUpdatePayload(account, partialPayload) {
  const hasApiKey = Object.prototype.hasOwnProperty.call(partialPayload, "api_key");
  const hasBrowserProxyUrl = Object.prototype.hasOwnProperty.call(partialPayload, "browser_proxy_url");
  const hasApiProxyUrl = Object.prototype.hasOwnProperty.call(partialPayload, "api_proxy_url");

  return {
    remark_name: Object.prototype.hasOwnProperty.call(partialPayload, "remark_name")
      ? partialPayload.remark_name
      : account.remark_name ?? null,
    browser_proxy_mode: partialPayload.browser_proxy_mode ?? account.browser_proxy_mode ?? "direct",
    browser_proxy_url: hasBrowserProxyUrl ? partialPayload.browser_proxy_url : account.browser_proxy_url ?? null,
    api_proxy_mode: partialPayload.api_proxy_mode ?? account.api_proxy_mode ?? "direct",
    api_proxy_url: hasApiProxyUrl ? partialPayload.api_proxy_url : account.api_proxy_url ?? null,
    api_key: hasApiKey ? partialPayload.api_key : account.api_key ?? null,
  };
}


function buildLoginDrawerAccount(account) {
  return {
    ...account,
    display_name: getDisplayName(account),
    browser_proxy_display: account.browser_proxy_display || buildProxyDisplay(account.browser_proxy_mode, account.browser_proxy_url, account.browser_public_ip),
    api_proxy_display: account.api_proxy_display || buildProxyDisplay(account.api_proxy_mode, account.api_proxy_url, account.api_public_ip),
  };
}


function buildQueryStatus(enabled, reasonCode = null, reasonText = null) {
  return {
    enabled,
    statusCode: enabled ? QUERY_STATUS_ENABLED : QUERY_STATUS_DISABLED,
    statusText: enabled ? "已启用" : "已禁用",
    reasonCode: enabled ? null : reasonCode,
    reasonText: enabled ? null : (reasonText || QUERY_REASON_TEXTS[reasonCode] || ""),
  };
}


function normalizeAccountCenterRow(row) {
  const hasApiKey = Boolean(row.api_key_present || row.api_key);
  const apiQueryEnabled = typeof row.api_query_enabled === "boolean"
    ? row.api_query_enabled
    : (
      hasApiKey
      && Boolean(row.new_api_enabled ?? true)
      && Boolean(row.fast_api_enabled ?? true)
      && row.api_key_status_code !== "ip_invalid"
    );
  const apiReasonCode = row.api_query_disable_reason_code
    || row.api_query_disabled_reason
    || (row.api_key_status_code === "ip_invalid" ? "ip_invalid" : null)
    || (!hasApiKey ? "missing_api_key" : null)
    || (apiQueryEnabled ? null : "manual_disabled");
  const apiReasonText = row.api_query_disable_reason_text
    || (row.api_key_status_code === "ip_invalid" ? row.api_key_status_text : null)
    || QUERY_REASON_TEXTS[apiReasonCode]
    || null;

  const browserQueryEnabled = typeof row.browser_query_enabled === "boolean"
    ? row.browser_query_enabled
    : (Boolean(row.token_enabled ?? true) && row.purchase_status_code !== "not_logged_in");
  const browserReasonCode = row.browser_query_disable_reason_code
    || row.browser_query_disabled_reason
    || ((!browserQueryEnabled && row.purchase_status_code === "not_logged_in") ? "not_logged_in" : null)
    || (browserQueryEnabled ? null : "manual_disabled");
  const browserReasonText = row.browser_query_disable_reason_text
    || QUERY_REASON_TEXTS[browserReasonCode]
    || null;

  const apiStatus = hasApiKey && apiQueryEnabled
    ? buildQueryStatus(true)
    : buildQueryStatus(false, apiReasonCode, apiReasonText);
  const browserStatus = browserQueryEnabled
    ? buildQueryStatus(true)
    : buildQueryStatus(false, browserReasonCode, browserReasonText);

  return {
    ...row,
    browser_proxy_display: row.browser_proxy_display || buildProxyDisplay(row.browser_proxy_mode, row.browser_proxy_url, row.browser_public_ip),
    api_proxy_display: row.api_proxy_display || buildProxyDisplay(row.api_proxy_mode, row.api_proxy_url, row.api_public_ip),
    api_key_present: hasApiKey,
    api_query_enabled: apiStatus.enabled,
    api_query_status_code: apiStatus.statusCode,
    api_query_status_text: apiStatus.statusText,
    api_query_disable_reason_code: apiStatus.reasonCode,
    api_query_disable_reason_text: apiStatus.reasonText,
    browser_query_enabled: browserStatus.enabled,
    browser_query_status_code: browserStatus.statusCode,
    browser_query_status_text: browserStatus.statusText,
    browser_query_disable_reason_code: browserStatus.reasonCode,
    browser_query_disable_reason_text: browserStatus.reasonText,
  };
}


function normalizeAccountRows(rows) {
  return Array.isArray(rows) ? rows.map(normalizeAccountCenterRow) : [];
}


function upsertAccountRow(rows, nextRow) {
  if (!nextRow) {
    return rows;
  }

  const nextRows = Array.isArray(rows) ? [...rows] : [];
  const rowIndex = nextRows.findIndex((row) => row.account_id === nextRow.account_id);
  if (rowIndex >= 0) {
    nextRows[rowIndex] = nextRow;
    return nextRows;
  }
  nextRows.push(nextRow);
  return nextRows;
}


function removeAccountRow(rows, accountId) {
  if (!accountId) {
    return rows;
  }
  return Array.isArray(rows) ? rows.filter((row) => row.account_id !== accountId) : rows;
}


function buildLoginTaskStatusText(account, taskSnapshot) {
  const displayName = getDisplayName(account);

  if (taskSnapshot.state === "succeeded" || taskSnapshot.state === "success") {
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

  if (taskSnapshot.state === "pending") {
    return `登录任务已创建：${displayName}`;
  }

  if (taskSnapshot.state) {
    return `登录任务状态更新：${displayName}`;
  }

  return `登录任务已创建：${displayName}`;
}


function getLatestTaskMessage(taskSnapshot) {
  return taskSnapshot.events?.[taskSnapshot.events.length - 1]?.message || taskSnapshot.error || "";
}


function stringifyLogValue(value) {
  if (value == null) {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}


function getLoginTaskMeta(taskSnapshot) {
  const lines = [];
  const selectedSteamId = taskSnapshot.result?.selected_steam_id
    || taskSnapshot.events?.[taskSnapshot.events.length - 1]?.payload?.selected_steam_id;

  if (selectedSteamId) {
    lines.push(selectedSteamId);
  }

  if (taskSnapshot.state) {
    lines.push(`状态：${taskSnapshot.state}`);
  }

  const latestMessage = getLatestTaskMessage(taskSnapshot);
  if (latestMessage) {
    lines.push(`回执：${latestMessage}`);
  }

  if (taskSnapshot.error) {
    lines.push(`错误：${taskSnapshot.error}`);
  }

  const latestPayload = taskSnapshot.events?.[taskSnapshot.events.length - 1]?.payload;
  if (latestPayload) {
    lines.push(`payload：${stringifyLogValue(latestPayload)}`);
  }

  if (taskSnapshot.result) {
    lines.push(`result：${stringifyLogValue(taskSnapshot.result)}`);
  }

  return lines;
}


function getErrorMeta(error) {
  if (!(error instanceof Error)) {
    return [];
  }

  const lines = [];

  if (error.status) {
    lines.push(`HTTP ${error.status}`);
  }

  if (error.method && error.path) {
    lines.push(`${error.method} ${error.path}`);
  }

  if (error.responseText) {
    lines.push(`原始返回：${error.responseText}`);
  }

  return lines;
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
  const [browserProxyDialogAccount, setBrowserProxyDialogAccount] = useState(null);
  const [proxyDialogAccount, setProxyDialogAccount] = useState(null);
  const [openingBindingAccountIds, setOpeningBindingAccountIds] = useState({});
  const [purchaseDrawerState, setPurchaseDrawerState] = useState({
    account: null,
    detail: null,
    isLoading: false,
    isRefreshing: false,
    open: false,
  });
  const openingBindingAccountIdsRef = useRef(new Set());
  const [loginDrawerAccount, setLoginDrawerAccount] = useState(null);
  const loginDrawerAccountRef = useRef(null);
  const loginTaskLogKeysRef = useRef(new Set());
  const [contextMenu, setContextMenu] = useState(null);
  const [accountLogs, setAccountLogs] = useState(INITIAL_LOG_ENTRIES);
  const loginTaskStream = useLoginTaskStream({ client });
  const logsModalState = useFloatingRuntimeModalState({
    initialPosition: { x: 168, y: 104 },
    initialSize: { width: 760, height: 520 },
  });

  function appendLogEntry(entry) {
    setAccountLogs((current) => [createLogEntry(entry), ...current]);
  }

  function appendErrorLog(message, meta = []) {
    appendLogEntry({
      title: "最近错误",
      message,
      meta,
    });
  }

  function appendLoginLog(message, meta = []) {
    appendLogEntry({
      title: "最近登录任务",
      message,
      meta,
    });
  }

  function appendModificationLog(message, meta = []) {
    appendLogEntry({
      title: "最近修改",
      message,
      meta,
    });
  }

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

        setRows(normalizeAccountRows(nextRows));
      } catch (error) {
        if (!isMounted) {
          return;
        }

        const message = toErrorMessage(error);
        setLoadError(message);
        appendErrorLog(`加载账号失败：${message}`, getErrorMeta(error));
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

  useEffect(() => {
    setProxyDialogAccount((current) => {
      if (!current) {
        return current;
      }
      return rows.find((row) => row.account_id === current.account_id) ?? current;
    });
  }, [rows]);

  const overviewCards = useMemo(() => buildOverviewCards(rows), [rows]);
  const filteredRows = useMemo(() => rows.filter((row) => (
    matchesFilter(row, uiState.activeFilter) && matchesSearch(row, uiState.searchTerm)
  )), [rows, uiState.activeFilter, uiState.searchTerm]);

  useEffect(() => {
    let cancelled = false;

    async function consumeAccountUpdates() {
      const streamFactory = client.watchAccountUpdates;
      if (typeof streamFactory !== "function") {
        return;
      }

      try {
        for await (const event of streamFactory.call(client)) {
          if (cancelled) {
            return;
          }
          const accountId = String(event?.account_id ?? "");
          if (!accountId) {
            continue;
          }
          if (event?.event === "delete_account") {
            setRows((currentRows) => removeAccountRow(currentRows, accountId));
            if (loginDrawerAccountRef.current?.account_id === accountId) {
              setLoginDrawerAccount(null);
            }
            setBrowserProxyDialogAccount((current) => (
              current?.account_id === accountId ? null : current
            ));
            setPurchaseDrawerState((current) => (
              current.account?.account_id === accountId
                ? {
                  account: null,
                  detail: null,
                  isLoading: false,
                  isRefreshing: false,
                  open: false,
                }
                : current
            ));
            setContextMenu((current) => (
              current?.account?.account_id === accountId ? null : current
            ));
            continue;
          }
          try {
            await refreshAccountCenterRow(accountId);
          } catch {
            if (cancelled) {
              return;
            }
          }
        }
      } catch {
        // Ignore push channel errors; manual refresh and task flow remain available.
      }
    }

    consumeAccountUpdates();
    return () => {
      cancelled = true;
    };
  }, [client]);

  async function refreshAccounts() {
    setIsLoading(true);
    setLoadError("");

    try {
      const nextRows = await client.listAccountCenterAccounts();
      const normalizedRows = normalizeAccountRows(nextRows);
      setRows(normalizedRows);
      return normalizedRows;
    } catch (error) {
      const message = toErrorMessage(error);
      setLoadError(message);
      appendErrorLog(`加载账号失败：${message}`, getErrorMeta(error));
      throw error;
    } finally {
      setIsLoading(false);
    }
  }

  async function refreshAccountCenterRow(accountId) {
    if (!accountId || typeof client.getAccountCenterAccount !== "function") {
      return null;
    }

    const nextAccount = normalizeAccountCenterRow(await client.getAccountCenterAccount(accountId));
    setRows((currentRows) => upsertAccountRow(currentRows, nextAccount));
    if (loginDrawerAccountRef.current?.account_id === accountId) {
      setLoginDrawerAccount(buildLoginDrawerAccount(nextAccount));
    }
    return nextAccount;
  }

  async function handleAction(action, successMessageBuilder) {
    try {
      const result = await action();
      const nextMessage = typeof successMessageBuilder === "function"
        ? successMessageBuilder(result)
        : successMessageBuilder;
      if (nextMessage) {
        appendModificationLog(nextMessage);
      }
      return result;
    } catch (error) {
      appendErrorLog(toErrorMessage(error), getErrorMeta(error));
      return null;
    }
  }

  async function runLoginForAccount(account) {
    const loginAccount = buildLoginDrawerAccount(account);
    setLoginDrawerAccount(loginAccount);

    try {
      return await loginTaskStream.start(loginAccount.account_id, {
        async onSnapshot(snapshot) {
          const logKey = `${snapshot.task_id}:${snapshot.state}`;
          if (!loginTaskLogKeysRef.current.has(logKey)) {
            loginTaskLogKeysRef.current.add(logKey);
            appendLoginLog(buildLoginTaskStatusText(loginAccount, snapshot), getLoginTaskMeta(snapshot));
          }

          if (snapshot.state === "failed") {
            appendErrorLog(`登录失败：${getLatestTaskMessage(snapshot) || "未知错误"}`, getLoginTaskMeta(snapshot));
          }
        },
        async onTerminal(snapshot) {
          if (snapshot.state === "succeeded" || snapshot.state === "success") {
            const nextRows = await refreshAccounts();
            const nextAccount = nextRows.find((row) => row.account_id === loginAccount.account_id);
            if (nextAccount && loginDrawerAccountRef.current?.account_id === loginAccount.account_id) {
              setLoginDrawerAccount(buildLoginDrawerAccount(nextAccount));
            }
          }
        },
      });
    } catch (error) {
      appendErrorLog(`发起登录失败：${toErrorMessage(error)}`, getErrorMeta(error));
      return null;
    }
  }

  async function openPurchaseStatus(account) {
    setContextMenu(null);

    if (isNotLoggedIn(account)) {
      setLoginDrawerAccount(buildLoginDrawerAccount(account));
      return null;
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
      return detail;
    } catch (error) {
      setPurchaseDrawerState({
        account: null,
        detail: null,
        isLoading: false,
        isRefreshing: false,
        open: false,
      });
      appendErrorLog(`加载购买配置失败：${toErrorMessage(error)}`, getErrorMeta(error));
      return null;
    }
  }

  async function toggleApiQueryMode(account) {
    setContextMenu(null);

    if (account.api_query_disable_reason_code === "missing_api_key" && !account.api_key_present) {
      setApiKeyDialogAccount(account);
      return null;
    }

    const nextEnabled = !account.api_query_enabled;
    return handleAction(async () => {
      await client.updateAccountQueryModes(account.account_id, nextEnabled
        ? { api_query_enabled: true }
        : {
          api_query_enabled: false,
          api_query_disabled_reason: "manual_disabled",
        });
      await refreshAccounts();
    }, `${nextEnabled ? "已启用" : "已禁用"} API 查询：${getDisplayName(account)}`);
  }

  async function toggleBrowserQueryMode(account) {
    setContextMenu(null);

    if (account.browser_query_disable_reason_code === "not_logged_in" && !account.browser_query_enabled) {
      return openPurchaseStatus(account);
    }

    const nextEnabled = !account.browser_query_enabled;
    return handleAction(async () => {
      await client.updateAccountQueryModes(account.account_id, nextEnabled
        ? { browser_query_enabled: true }
        : {
          browser_query_enabled: false,
          browser_query_disabled_reason: "manual_disabled",
        });
      await refreshAccounts();
    }, `${nextEnabled ? "已启用" : "已禁用"} 浏览器查询：${getDisplayName(account)}`);
  }

  return {
    activeFilter: uiState.activeFilter,
    accountLogs,
    apiKeyDialogAccount,
    closeApiKeyDialog() {
      setApiKeyDialogAccount(null);
    },
    closeBrowserProxyDialog() {
      setBrowserProxyDialogAccount(null);
    },
    closeContextMenu() {
      setContextMenu(null);
    },
    closeCreateDialog() {
      setCreateDialogOpen(false);
    },
    closeLoginDrawer() {
      setLoginDrawerAccount(null);
      loginTaskLogKeysRef.current.clear();
      loginTaskStream.reset();
    },
    logsModalState,
    browserProxyDialogAccount,
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
    openLogsModal: logsModalState.onOpen,
    openApiKeyDialog(account) {
      setApiKeyDialogAccount(account);
      setContextMenu(null);
    },
    openBrowserProxyDialog(account) {
      setBrowserProxyDialogAccount(account);
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
    openAccountOpenApiBindingPage: async (account) => {
      const accountId = String(account?.account_id || "");
      setContextMenu(null);
      if (!accountId || openingBindingAccountIdsRef.current.has(accountId)) {
        return null;
      }
      openingBindingAccountIdsRef.current.add(accountId);
      setOpeningBindingAccountIds((current) => ({
        ...current,
        [accountId]: true,
      }));
      try {
        return await handleAction(async () => {
          await client.openAccountOpenApiBindingPage(accountId);
        }, `已打开 API 绑定页：${getDisplayName(account)}`);
      } finally {
        openingBindingAccountIdsRef.current.delete(accountId);
        setOpeningBindingAccountIds((current) => {
          if (!current[accountId]) {
            return current;
          }
          const next = { ...current };
          delete next[accountId];
          return next;
        });
      }
    },
    syncAccountOpenApi: async (account) => {
      setContextMenu(null);
      return handleAction(async () => {
        await client.syncAccountOpenApi(account.account_id);
        await refreshAccounts();
      }, `已重新同步 API 白名单：${getDisplayName(account)}`);
    },
    openNicknameDialog(account) {
      setRemarkDialogAccount(account);
      setContextMenu(null);
    },
    openProxyDialog(account) {
      setProxyDialogAccount(account);
      setContextMenu(null);
    },
    openPurchaseStatus,
    isOpeningBindingPage: Boolean(
      proxyDialogAccount && openingBindingAccountIds[String(proxyDialogAccount.account_id || "")]
    ),
    overviewCards,
    proxyDialogAccount,
    purchaseDrawerState,
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
    toggleApiQueryMode,
    toggleBrowserQueryMode,
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
    submitBrowserProxy: async (payload) => {
      const account = browserProxyDialogAccount;
      if (!account) {
        return null;
      }

      const browserProxyChanged = account.browser_proxy_mode !== payload.browser_proxy_mode
        || (account.browser_proxy_url ?? "") !== (payload.browser_proxy_url ?? "");

      if (!browserProxyChanged) {
        setBrowserProxyDialogAccount(null);
        return account;
      }

      try {
        await client.updateAccount(account.account_id, buildAccountUpdatePayload(account, payload));
        await client.clearPurchaseCapability(account.account_id);
        setBrowserProxyDialogAccount(null);
        appendModificationLog(`已更新浏览器代理，账号进入未登录状态：${getDisplayName(account)}`);
        const nextRows = await refreshAccounts();
        const nextAccount = nextRows.find((row) => row.account_id === account.account_id) ?? account;
        await runLoginForAccount(nextAccount);
        return nextAccount;
      } catch (error) {
        appendErrorLog(toErrorMessage(error), getErrorMeta(error));
        return null;
      }
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

      const apiProxyChanged = account.api_proxy_mode !== payload.api_proxy_mode
        || (account.api_proxy_url ?? "") !== (payload.api_proxy_url ?? "");

      return handleAction(async () => {
        await client.updateAccount(account.account_id, buildAccountUpdatePayload(account, payload));
        if (apiProxyChanged) {
          await client.syncAccountOpenApi(account.account_id);
        }
        setProxyDialogAccount(null);
        await refreshAccounts();
      }, `${apiProxyChanged ? "已更新 API 代理并刷新白名单" : "已更新 API 代理"}：${getDisplayName(account)}`);
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
        let nextAccount = account;
        try {
          nextAccount = await refreshAccountCenterRow(account.account_id) ?? account;
        } catch (syncError) {
          appendErrorLog(`同步购买状态失败：${toErrorMessage(syncError)}`, getErrorMeta(syncError));
        }
        setPurchaseDrawerState((current) => ({
          ...current,
          account: nextAccount,
          detail,
          isLoading: false,
          isRefreshing: false,
          open: true,
        }));
        appendModificationLog(`已刷新仓库：${getDisplayName(account)}`);
        return detail;
      } catch (error) {
        setPurchaseDrawerState((current) => ({
          ...current,
          isRefreshing: false,
        }));
        appendErrorLog(`刷新仓库失败：${toErrorMessage(error)}`, getErrorMeta(error));
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
