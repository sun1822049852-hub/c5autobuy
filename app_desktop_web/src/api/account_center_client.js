import { getDesktopBootstrapConfig } from "../desktop/bridge.js";
import { createHttpClient } from "./http.js";


const TERMINAL_TASK_STATES = new Set(["succeeded", "failed", "cancelled", "conflict"]);


function buildWebSocketUrl(apiBaseUrl, taskId) {
  try {
    const url = new URL(apiBaseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `/ws/tasks/${taskId}`;
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return null;
  }
}


async function* streamTaskViaWebSocket(url, WebSocketImpl) {
  let closedError = null;
  let connectionReject = null;
  let connectionResolve = null;
  let pendingResolver = null;
  const queue = [];
  const readyPromise = new Promise((resolve, reject) => {
    connectionResolve = resolve;
    connectionReject = reject;
  });
  const websocket = new WebSocketImpl(url);

  websocket.onopen = () => {
    connectionResolve?.();
  };
  websocket.onerror = () => {
    const error = new Error("WebSocket 任务流连接失败");
    if (pendingResolver) {
      pendingResolver.reject(error);
      pendingResolver = null;
    }
    if (connectionReject) {
      connectionReject(error);
      connectionReject = null;
    } else {
      closedError = error;
    }
  };
  websocket.onclose = () => {
    const error = new Error("WebSocket 任务流已关闭");
    if (pendingResolver) {
      pendingResolver.reject(error);
      pendingResolver = null;
    } else {
      closedError = error;
    }
  };
  websocket.onmessage = (event) => {
    const payload = JSON.parse(typeof event.data === "string" ? event.data : String(event.data ?? ""));
    if (pendingResolver) {
      pendingResolver.resolve(payload);
      pendingResolver = null;
      return;
    }

    queue.push(payload);
  };

  await readyPromise;

  while (true) {
    if (closedError) {
      throw closedError;
    }

    const snapshot = queue.length
      ? queue.shift()
      : await new Promise((resolve, reject) => {
        pendingResolver = { resolve, reject };
      });

    yield snapshot;

    if (TERMINAL_TASK_STATES.has(snapshot.state)) {
      websocket.close();
      return;
    }
  }
}


export function createAccountCenterClient({
  apiBaseUrl,
  fetchImpl,
  pollIntervalMs = 50,
  sleepImpl = (delayMs) => new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  }),
  WebSocketImpl = globalThis.WebSocket,
} = {}) {
  const bootstrapConfig = getDesktopBootstrapConfig();
  const resolvedApiBaseUrl = apiBaseUrl ?? bootstrapConfig.apiBaseUrl;
  const http = createHttpClient({
    baseUrl: resolvedApiBaseUrl,
    fetchImpl,
  });

  return {
    async listAccountCenterAccounts() {
      return http.getJson("/account-center/accounts", {
        method: "GET",
      });
    },
    async listQueryConfigs() {
      return http.getJson("/query-configs", {
        method: "GET",
      });
    },
    async getQueryConfig(configId) {
      return http.getJson(`/query-configs/${configId}`, {
        method: "GET",
      });
    },
    async getQueryCapacitySummary() {
      return http.getJson("/query-configs/capacity-summary", {
        method: "GET",
      });
    },
    async getQueryRuntimeStatus() {
      return http.getJson("/query-runtime/status", {
        method: "GET",
      });
    },
    async getPurchaseRuntimeStatus() {
      return http.getJson("/purchase-runtime/status", {
        method: "GET",
      });
    },
    async startQueryRuntime(configId) {
      return http.postJson("/query-runtime/start", {
        config_id: configId,
      });
    },
    async stopQueryRuntime() {
      return http.postJson("/query-runtime/stop", {});
    },
    async startPurchaseRuntime(configId) {
      return http.postJson("/purchase-runtime/start", {
        config_id: configId,
      });
    },
    async stopPurchaseRuntime() {
      return http.postJson("/purchase-runtime/stop", {});
    },
    async createQueryConfig(payload) {
      return http.postJson("/query-configs", payload);
    },
    async deleteQueryConfig(configId) {
      await http.delete(`/query-configs/${configId}`);
    },
    async addQueryItem(configId, payload) {
      return http.postJson(`/query-configs/${configId}/items`, payload);
    },
    async updateQueryItem(configId, queryItemId, payload) {
      return http.patchJson(`/query-configs/${configId}/items/${queryItemId}`, payload);
    },
    async deleteQueryItem(configId, queryItemId) {
      await http.delete(`/query-configs/${configId}/items/${queryItemId}`);
    },
    async applyQueryItemRuntime(configId, queryItemId) {
      return http.postJson(`/query-configs/${configId}/items/${queryItemId}/apply-runtime`, {});
    },
    async parseQueryItemUrl(productUrl) {
      return http.postJson("/query-items/parse-url", {
        product_url: productUrl,
      });
    },
    async fetchQueryItemDetail(payload) {
      return http.postJson("/query-items/fetch-detail", payload);
    },
    async createAccount(payload) {
      return http.postJson("/accounts", payload);
    },
    async updateAccount(accountId, payload) {
      return http.patchJson(`/accounts/${accountId}`, payload);
    },
    async updateAccountPurchaseConfig(accountId, payload) {
      return http.patchJson(`/accounts/${accountId}/purchase-config`, payload);
    },
    async deleteAccount(accountId) {
      await http.delete(`/accounts/${accountId}`);
    },
    async startLogin(accountId) {
      return http.postJson(`/accounts/${accountId}/login`, {});
    },
    async getPurchaseRuntimeInventoryDetail(accountId) {
      return http.getJson(`/purchase-runtime/accounts/${accountId}/inventory`, {
        method: "GET",
      });
    },
    async refreshPurchaseRuntimeInventoryDetail(accountId) {
      return http.getJson(`/purchase-runtime/accounts/${accountId}/inventory/refresh`, {
        method: "POST",
      });
    },
    async getTask(taskId) {
      return http.getJson(`/tasks/${taskId}`, {
        method: "GET",
      });
    },
    async *watchTask(taskId) {
      const canUseWebSocket = Boolean(WebSocketImpl)
        && globalThis.window?.location?.protocol !== "about:";
      const websocketUrl = buildWebSocketUrl(resolvedApiBaseUrl, taskId);

      if (canUseWebSocket && websocketUrl) {
        try {
          yield* streamTaskViaWebSocket(websocketUrl, WebSocketImpl);
          return;
        } catch {
          // WebSocket 不可用时回退到轮询，避免桌面端直接失联。
        }
      }

      let lastSignature = null;

      while (true) {
        const snapshot = await http.getJson(`/tasks/${taskId}`, {
          method: "GET",
        });
        const signature = [
          snapshot.state,
          snapshot.updated_at,
          snapshot.error,
          snapshot.events?.length ?? 0,
        ].join(":");

        if (signature !== lastSignature) {
          yield snapshot;
          lastSignature = signature;
        }

        if (TERMINAL_TASK_STATES.has(snapshot.state)) {
          return;
        }

        await sleepImpl(pollIntervalMs);
      }
    },
  };
}
