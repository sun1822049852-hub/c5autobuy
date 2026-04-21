// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";
import { createAppRuntimeStore } from "../../src/runtime/app_runtime_store.js";


function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}


function installDesktopApp(fetchImpl) {
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        apiBaseUrl: "http://127.0.0.1:8123",
        backendStatus: "ready",
      };
    },
  };
}


function buildReadonlyLockedRuntimeStore() {
  const runtimeStore = createAppRuntimeStore();
  runtimeStore.applyProgramAccess({
    mode: "remote_entitlement",
    stage: "packaged_release",
    guard_enabled: true,
    message: "请先登录程序会员",
    auth_state: null,
    runtime_state: "stopped",
    last_error_code: "program_auth_required",
  });
  return runtimeStore;
}


function buildIdleRuntimeStatus() {
  return {
    running: false,
    config_id: null,
    config_name: null,
    message: "未运行",
    account_count: 0,
    started_at: null,
    stopped_at: null,
    total_query_count: 0,
    total_found_count: 0,
    modes: {},
    group_rows: [],
    recent_events: [],
    item_rows: [],
  };
}

function buildRunningRuntimeStatus({
  configId = "cfg-1",
  configName = "白天配置",
  queryCount = 74,
} = {}) {
  return {
    ...buildIdleRuntimeStatus(),
    running: true,
    config_id: configId,
    config_name: configName,
    message: "运行中",
    total_query_count: queryCount,
    item_rows: [
      {
        query_item_id: "item-1",
        item_name: "P90 | 满晕作品 (久经沙场)",
        max_price: 0.4,
        min_wear: 0.15,
        max_wear: 0.28,
        detail_min_wear: 0.15,
        detail_max_wear: 0.28,
        manual_paused: false,
        query_count: queryCount,
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 2,
            actual_dedicated_count: 2,
            status: "running",
            status_message: "运行中",
          },
        },
      },
    ],
  };
}

function buildIdlePurchaseStatus() {
  return {
    running: false,
    message: "未运行",
    started_at: null,
    stopped_at: null,
    queue_size: 0,
    active_account_count: 0,
    total_account_count: 0,
    total_purchased_count: 0,
    runtime_session_id: null,
    active_query_config: null,
    matched_product_count: 0,
    purchase_success_count: 0,
    purchase_failed_count: 0,
    recent_events: [],
    accounts: [],
    item_rows: [],
  };
}

function buildRunningPurchaseStatus({
  configId = "cfg-1",
  configName = "白天配置",
  queryExecutionCount = 74,
} = {}) {
  return {
    ...buildIdlePurchaseStatus(),
    running: true,
    message: "运行中",
    started_at: "2026-03-19T12:00:00",
    queue_size: 1,
    active_account_count: 1,
    total_account_count: 1,
    runtime_session_id: "runtime-1",
    active_query_config: {
      config_id: configId,
      config_name: configName,
      state: "running",
      message: "运行中",
    },
    item_rows: [
      {
        query_item_id: "item-1",
        item_name: "P90 | 满晕作品 (久经沙场)",
        max_price: 0.4,
        min_wear: 0.15,
        max_wear: 0.28,
        detail_min_wear: 0.15,
        detail_max_wear: 0.28,
        manual_paused: false,
        query_execution_count: queryExecutionCount,
        matched_product_count: 0,
        purchase_success_count: 0,
        purchase_failed_count: 0,
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 2,
            actual_dedicated_count: 2,
            status: "running",
            status_message: "运行中",
            shared_available_count: 0,
          },
        },
        source_mode_stats: [],
        recent_hit_sources: [],
      },
    ],
  };
}


function createFetchHarness({ initialRuntimeStatus, initialPurchaseStatus } = {}) {
  const configs = [
    {
      config_id: "cfg-1",
      name: "白天配置",
      description: "白天轮询",
      enabled: true,
      created_at: "2026-03-19T10:00:00",
      updated_at: "2026-03-19T10:00:00",
      items: [],
      mode_settings: [],
    },
    {
      config_id: "cfg-2",
      name: "夜刀配置",
      description: "夜间专用",
      enabled: true,
      created_at: "2026-03-19T11:00:00",
      updated_at: "2026-03-19T11:00:00",
      items: [],
      mode_settings: [],
    },
  ];

  const details = Object.fromEntries(configs.map((config) => [config.config_id, config]));
  let runtimeStatus = initialRuntimeStatus || buildIdleRuntimeStatus();
  let purchaseRuntimeStatus = initialPurchaseStatus || buildIdlePurchaseStatus();
  const calls = [];
  let createdCount = 3;

  const fetchImpl = vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();
    const body = typeof options.body === "string" ? JSON.parse(options.body) : null;
    calls.push({
      body,
      method,
      pathname: url.pathname,
    });

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(configs);
    }
    if (url.pathname === "/query-configs" && method === "POST") {
      const created = {
        config_id: `cfg-${createdCount}`,
        name: body.name,
        description: body.description,
        enabled: true,
        created_at: "2026-03-19T12:00:00",
        updated_at: "2026-03-19T12:00:00",
        items: [],
        mode_settings: [],
      };
      createdCount += 1;
      configs.push(created);
      details[created.config_id] = created;
      return jsonResponse(created, 201);
    }
    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse({
        modes: {
          new_api: { mode_type: "new_api", available_account_count: 2 },
          fast_api: { mode_type: "fast_api", available_account_count: 1 },
          token: { mode_type: "token", available_account_count: 3 },
        },
      });
    }
    if (url.pathname === "/query-runtime/status" && method === "GET") {
      return jsonResponse(runtimeStatus);
    }
    if (url.pathname === "/purchase-runtime/status" && method === "GET") {
      return jsonResponse(purchaseRuntimeStatus);
    }
    if (url.pathname === "/purchase-runtime/ui-preferences" && method === "GET") {
      return jsonResponse({
        selected_config_id: purchaseRuntimeStatus.active_query_config?.config_id || "cfg-1",
        updated_at: "2026-03-19T12:00:00",
      });
    }
    if (url.pathname === "/runtime-settings/purchase" && method === "GET") {
      return jsonResponse({
        per_batch_ip_fanout_limit: 1,
        updated_at: "2026-03-19T12:00:00",
      });
    }
    if (url.pathname === "/query-runtime/start" && method === "POST") {
      const nextConfig = details[body.config_id];
      runtimeStatus = {
        ...buildIdleRuntimeStatus(),
        running: true,
        config_id: body.config_id,
        config_name: nextConfig.name,
        message: "运行中",
      };
      return jsonResponse(runtimeStatus);
    }
    if (url.pathname === "/query-runtime/stop" && method === "POST") {
      runtimeStatus = buildIdleRuntimeStatus();
      return jsonResponse(runtimeStatus);
    }

    const match = url.pathname.match(/^\/query-configs\/([^/]+)$/);
    if (match && method === "GET") {
      return jsonResponse(details[match[1]]);
    }
    if (match && method === "DELETE") {
      const configId = match[1];
      const configIndex = configs.findIndex((config) => config.config_id === configId);
      if (configIndex >= 0) {
        configs.splice(configIndex, 1);
      }
      delete details[configId];
      if (runtimeStatus.config_id === configId) {
        runtimeStatus = buildIdleRuntimeStatus();
      }
      return jsonResponse({}, 204);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
    setPurchaseRuntimeStatus(nextStatus) {
      purchaseRuntimeStatus = nextStatus;
    },
    setRuntimeStatus(nextStatus) {
      runtimeStatus = nextStatus;
    },
  };
}


function buildHydratedQueryRuntimeStore({ configOverrides = {}, draftOverrides = {} } = {}) {
  const store = createAppRuntimeStore();
  const hydratedConfig = {
    config_id: "cfg-1",
    name: "白天配置",
    description: "白天轮询",
    enabled: true,
    created_at: "2026-03-19T10:00:00",
    updated_at: "2026-03-19T10:00:00",
    items: [],
    mode_settings: [],
    serverShape: "detail",
    ...configOverrides,
  };

  store.applyBootstrap({
    querySystem: {
      server: {
        configs: [hydratedConfig],
        capacitySummary: {
          modes: {
            new_api: { mode_type: "new_api", available_account_count: 2 },
            fast_api: { mode_type: "fast_api", available_account_count: 1 },
            token: { mode_type: "token", available_account_count: 3 },
          },
        },
        runtimeStatus: buildIdleRuntimeStatus(),
      },
    },
  });
  store.patchQueryUi({ selectedConfigId: "cfg-1" });
  store.patchQueryDraft({
    currentConfig: {
      ...hydratedConfig,
      ...draftOverrides,
    },
    hasUnsavedChanges: false,
  });

  return store;
}


function buildEmptyHydratedQueryRuntimeStore() {
  const store = createAppRuntimeStore();

  store.applyBootstrap({
    querySystem: {
      server: {
        configs: [],
        capacitySummary: { modes: {} },
        runtimeStatus: {
          running: false,
          item_rows: [],
        },
      },
    },
  });

  return store;
}


function findQueryPayloadCalls(calls) {
  return calls.filter((call) => [
    "/query-configs",
    "/query-configs/capacity-summary",
    "/query-runtime/status",
    "/query-configs/cfg-2",
    "/query-configs/cfg-1",
  ].includes(call.pathname));
}


describe("query system page", () => {
  it("prefers store-backed selected config during cold load before persisted or fallback ids", async () => {
    const harness = createFetchHarness();
    const runtimeStore = createAppRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    runtimeStore.patchQueryUi({ selectedConfigId: "cfg-2" });

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: null,
          method: "GET",
          pathname: "/query-configs/cfg-2",
        }),
      ]),
    );
  });

  it("does not refetch full query page payload when query store is empty but already hydrated", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildEmptyHydratedQueryRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByText("当前配置")).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByText("当前配置")).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);
  });

  it("does not background reload or reset transient query state while the keep-alive page is hidden", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    await user.click(screen.getByRole("button", { name: "新建配置" }));
    const createDialog = await screen.findByRole("dialog", { name: "新建配置" });
    await user.type(within(createDialog).getByLabelText("配置名称"), "alpha");

    const queryPayloadCallsBeforeHide = findQueryPayloadCalls(harness.calls).length;
    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    act(() => {
      runtimeStore.applyQuerySystemServer({
        configs: [
          {
            config_id: "cfg-1",
            name: "白天配置-已推送",
            description: "白天轮询",
            enabled: true,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T10:00:00",
            items: [],
            mode_settings: [],
          },
        ],
      });
    });

    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(queryPayloadCallsBeforeHide);

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    const restoredDialog = await screen.findByRole("dialog", { name: "新建配置" });
    expect(within(restoredDialog).getByLabelText("配置名称")).toHaveValue("alpha");
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(queryPayloadCallsBeforeHide);
  });

  it("re-evaluates query state when the hidden keep-alive page becomes active again", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    act(() => {
      runtimeStore.patchQueryUi({ selectedConfigId: "cfg-2" });
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: null,
          method: "GET",
          pathname: "/query-configs/cfg-2",
        }),
      ]),
    );
  });

  it("syncs the workbench to updated server content for the same config id when showing again without local edits", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    const queryPayloadCallsBeforeShow = findQueryPayloadCalls(harness.calls).length;
    act(() => {
      runtimeStore.applyQuerySystemServer({
        configs: [
          {
            config_id: "cfg-1",
            name: "白天配置-已推送",
            description: "白天轮询",
            enabled: true,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T12:00:00",
            items: [
              {
                query_item_id: "item-1",
                config_id: "cfg-1",
                product_url: "https://example.com/item-1",
                external_item_id: "item-1",
                item_name: "AK-47 | Redline",
                market_hash_name: "AK-47 | Redline (Field-Tested)",
                min_wear: 0.1,
                max_wear: 0.7,
                detail_min_wear: 0.1,
                detail_max_wear: 0.25,
                max_price: 199,
                last_market_price: 188.88,
                last_detail_sync_at: "2026-03-19T12:00:00",
                manual_paused: false,
                mode_allocations: [],
                sort_order: 0,
                created_at: "2026-03-19T10:00:00",
                updated_at: "2026-03-19T12:00:00",
              },
            ],
            mode_settings: [],
            serverShape: "detail",
          },
        ],
      });
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "白天配置-已推送" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "商品 AK-47 | Redline" })).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(queryPayloadCallsBeforeShow);
  });

  it("syncs authoritative empty detail items for the same config id when showing again without local edits", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore({
      configOverrides: {
        items: [
          {
            query_item_id: "item-1",
            config_id: "cfg-1",
            product_url: "https://example.com/item-1",
            external_item_id: "item-1",
            item_name: "AK-47 | Redline",
            market_hash_name: "AK-47 | Redline (Field-Tested)",
            min_wear: 0.1,
            max_wear: 0.7,
            detail_min_wear: 0.1,
            detail_max_wear: 0.25,
            max_price: 199,
            last_market_price: 188.88,
            last_detail_sync_at: "2026-03-19T10:00:00",
            manual_paused: false,
            mode_allocations: [],
            sort_order: 0,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T10:00:00",
          },
        ],
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "商品 AK-47 | Redline" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    const queryPayloadCallsBeforeShow = findQueryPayloadCalls(harness.calls).length;
    act(() => {
      runtimeStore.applyQuerySystemServer({
        configs: [
          {
            config_id: "cfg-1",
            name: "白天配置-清空",
            description: "白天轮询",
            enabled: true,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T12:30:00",
            items: [],
            mode_settings: [],
            serverShape: "detail",
          },
        ],
      });
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "白天配置-清空" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "商品配置列表" })).toHaveTextContent("当前配置还没有商品，先从右上角 + 添加一件。");
    expect(screen.queryByRole("region", { name: "商品 AK-47 | Redline" })).not.toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(queryPayloadCallsBeforeShow);
  });

  it("treats external same-id pushes without serverShape as summary instead of silently clearing detail items", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore({
      configOverrides: {
        items: [
          {
            query_item_id: "item-1",
            config_id: "cfg-1",
            product_url: "https://example.com/item-1",
            external_item_id: "item-1",
            item_name: "AK-47 | Redline",
            market_hash_name: "AK-47 | Redline (Field-Tested)",
            min_wear: 0.1,
            max_wear: 0.7,
            detail_min_wear: 0.1,
            detail_max_wear: 0.25,
            max_price: 199,
            last_market_price: 188.88,
            last_detail_sync_at: "2026-03-19T10:00:00",
            manual_paused: false,
            mode_allocations: [],
            sort_order: 0,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T10:00:00",
          },
        ],
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "商品 AK-47 | Redline" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    const queryPayloadCallsBeforeShow = findQueryPayloadCalls(harness.calls).length;
    act(() => {
      runtimeStore.applyQuerySystemServer({
        configs: [
          {
            config_id: "cfg-1",
            name: "白天配置-外部摘要",
            description: "白天轮询",
            enabled: true,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T12:45:00",
            items: [],
            mode_settings: [],
          },
        ],
      });
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "白天配置-外部摘要" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "商品 AK-47 | Redline" })).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(queryPayloadCallsBeforeShow);
  });

  it("does not refetch full query page payload when entering and re-entering with hydrated runtime store", async () => {
    const harness = createFetchHarness();
    const runtimeStore = buildHydratedQueryRuntimeStore();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);

    await screen.findByText("C5 交易助手");
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByText("C5 交易助手");

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    expect(findQueryPayloadCalls(harness.calls)).toHaveLength(0);
  });

  it("switches from account center into the real query system page and renders the skeleton", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("C5 交易助手")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    expect(nav).toBeInTheDocument();
    const currentConfigSection = screen.getByText("当前配置").closest("section");
    expect(screen.queryByText("查询工作台")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建配置" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "切换配置删除模式" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "启动当前配置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
    expect(within(nav).getByText("白天配置")).toBeInTheDocument();
    expect(within(nav).getByText("夜刀配置")).toBeInTheDocument();
    expect(screen.getByText("当前配置")).toBeInTheDocument();
    expect(currentConfigSection).not.toBeNull();
    expect(within(currentConfigSection).getByText("已停止")).toBeInTheDocument();
    expect(within(currentConfigSection).getByText("未运行")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    expect(screen.getByText("new_api 2")).toBeInTheDocument();
    expect(screen.getByText("token 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "添加商品" })).toBeInTheDocument();
    expect(screen.getByText("商品名")).toBeInTheDocument();
    expect(screen.getByText("市场价")).toBeInTheDocument();
    expect(screen.getByText("扫货价")).toBeInTheDocument();
    expect(screen.getByText("磨损")).toBeInTheDocument();
  });

  it("creates and deletes configs through centered dialogs", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    await user.click(screen.getByRole("button", { name: "新建配置" }));

    const createDialog = await screen.findByRole("dialog", { name: "新建配置" });
    await user.type(within(createDialog).getByLabelText("配置名称"), "新建夜巡配置");
    await user.type(within(createDialog).getByLabelText("配置说明"), "给夜间用");
    await user.click(within(createDialog).getByRole("button", { name: "保存配置" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "新建夜巡配置" })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    expect(within(nav).getByText("新建夜巡配置")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "切换配置删除模式" }));
    await user.click(within(nav).getByRole("button", { name: "删除配置 夜刀配置" }));
    const deleteDialog = await screen.findByRole("dialog", { name: "删除配置" });
    expect(within(deleteDialog).getByText("夜刀配置")).toBeInTheDocument();
    await user.click(within(deleteDialog).getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(within(nav).queryByText("夜刀配置")).not.toBeInTheDocument();
    });

    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: { description: "给夜间用", name: "新建夜巡配置" },
          method: "POST",
          pathname: "/query-configs",
        }),
        expect.objectContaining({
          body: null,
          method: "DELETE",
          pathname: "/query-configs/cfg-2",
        }),
      ]),
    );
  });

  it("loads the selected config detail when switching config items in the left nav", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    await user.click(within(nav).getByRole("button", { name: /^夜刀配置/ }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    });
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: null,
          method: "GET",
          pathname: "/query-configs/cfg-2",
        }),
      ]),
    );
  });

  it("keeps config browsing available but disables readonly mutations when program access is locked", async () => {
    const runtimeStore = buildHydratedQueryRuntimeStore({
      configOverrides: {
        items: [
          {
            query_item_id: "item-1",
            config_id: "cfg-1",
            product_url: "https://example.com/item-1",
            external_item_id: "item-1",
            item_name: "AK-47 | Redline",
            market_hash_name: "AK-47 | Redline (Field-Tested)",
            min_wear: 0.1,
            max_wear: 0.7,
            detail_min_wear: 0.1,
            detail_max_wear: 0.25,
            max_price: 199,
            last_market_price: 188.88,
            last_detail_sync_at: "2026-03-19T10:00:00",
            manual_paused: false,
            mode_allocations: [],
            sort_order: 0,
            created_at: "2026-03-19T10:00:00",
            updated_at: "2026-03-19T10:00:00",
          },
        ],
      },
    });
    runtimeStore.applyProgramAccess({
      mode: "remote_entitlement",
      stage: "packaged_release",
      guard_enabled: true,
      message: "请先登录程序会员",
      auth_state: null,
      runtime_state: "stopped",
      last_error_code: "program_auth_required",
    });
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App runtimeStore={runtimeStore} />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /^白天配置/ })).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "新建配置" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "切换配置删除模式" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "已保存" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "添加商品" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "切换商品删除模式" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "修改扫货价 AK-47 | Redline" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "修改磨损 AK-47 | Redline" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "切换手动暂停 AK-47 | Redline" })).toBeDisabled();
  });

  it("shows waiting status when backend reports a config is waiting for accounts", async () => {
    const harness = createFetchHarness({
      initialRuntimeStatus: {
        ...buildIdleRuntimeStatus(),
        config_id: "cfg-2",
        config_name: "夜刀配置",
        message: "等待购买账号恢复",
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    expect(within(nav).getByRole("button", { name: /^夜刀配置/ })).toHaveTextContent("等待账号");
    const currentConfigSection = screen.getByText("当前配置").closest("section");
    expect(currentConfigSection).not.toBeNull();
    expect(within(currentConfigSection).getByText("等待账号")).toBeInTheDocument();
    expect(screen.getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
  });

  it("shows backend runtime ownership but keeps query page as config-only management", async () => {
    const harness = createFetchHarness({
      initialRuntimeStatus: {
        ...buildIdleRuntimeStatus(),
        running: true,
        config_id: "cfg-1",
        config_name: "白天配置",
        message: "运行中",
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    expect(within(nav).getByRole("button", { name: /^白天配置/ })).toHaveTextContent("运行中");
    expect(within(nav).getByRole("button", { name: /^夜刀配置/ })).toHaveTextContent("已停止");
    expect(screen.queryByRole("button", { name: "启动当前配置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
  });

  it("syncs query config runtime badges after the purchase page hydrates a running runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "配置管理" }));

    const initialHeader = await screen.findByRole("heading", { name: "白天配置" });
    const initialSection = initialHeader.closest("section");
    expect(initialSection).not.toBeNull();
    expect(within(initialSection).getByText("已停止")).toBeInTheDocument();

    act(() => {
      harness.setRuntimeStatus(buildRunningRuntimeStatus());
      harness.setPurchaseRuntimeStatus(buildRunningPurchaseStatus());
    });

    await user.click(screen.getByRole("button", { name: "扫货系统" }));
    expect(await screen.findByRole("button", { name: "停止扫货" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    const syncedHeader = await screen.findByRole("heading", { name: "白天配置" });
    const syncedSection = syncedHeader.closest("section");
    expect(syncedSection).not.toBeNull();
    expect(within(syncedSection).getAllByText("运行中").length).toBeGreaterThan(0);
  });
});
