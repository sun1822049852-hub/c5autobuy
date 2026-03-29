// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


const ALL_MODES = ["new_api", "fast_api", "token"];

const QUERY_CONFIGS = [
  {
    config_id: "cfg-1",
    name: "白天配置",
    description: "白天轮询",
    enabled: true,
    created_at: "2026-03-20T09:00:00",
    updated_at: "2026-03-20T09:00:00",
    items: [],
    mode_settings: [],
  },
  {
    config_id: "cfg-2",
    name: "夜刀配置",
    description: "夜间专用",
    enabled: true,
    created_at: "2026-03-20T09:05:00",
    updated_at: "2026-03-20T09:05:00",
    items: [],
    mode_settings: [],
  },
];

const QUERY_SETTINGS = {
  modes: [
    {
      mode_type: "new_api",
      enabled: true,
      window_enabled: false,
      start_hour: 0,
      start_minute: 0,
      end_hour: 0,
      end_minute: 0,
      base_cooldown_min: 1,
      base_cooldown_max: 1,
      item_min_cooldown_seconds: 0.5,
      item_min_cooldown_strategy: "divide_by_assigned_count",
      random_delay_enabled: false,
      random_delay_min: 0,
      random_delay_max: 0,
      created_at: "2026-03-22T10:00:00",
      updated_at: "2026-03-22T10:00:00",
    },
    {
      mode_type: "fast_api",
      enabled: true,
      window_enabled: false,
      start_hour: 0,
      start_minute: 0,
      end_hour: 0,
      end_minute: 0,
      base_cooldown_min: 0.2,
      base_cooldown_max: 0.2,
      item_min_cooldown_seconds: 0.5,
      item_min_cooldown_strategy: "divide_by_assigned_count",
      random_delay_enabled: false,
      random_delay_min: 0,
      random_delay_max: 0,
      created_at: "2026-03-22T10:00:00",
      updated_at: "2026-03-22T10:00:00",
    },
    {
      mode_type: "token",
      enabled: true,
      window_enabled: false,
      start_hour: 0,
      start_minute: 0,
      end_hour: 0,
      end_minute: 0,
      base_cooldown_min: 10,
      base_cooldown_max: 10,
      item_min_cooldown_seconds: 0.5,
      item_min_cooldown_strategy: "divide_by_assigned_count",
      random_delay_enabled: false,
      random_delay_min: 0,
      random_delay_max: 0,
      created_at: "2026-03-22T10:00:00",
      updated_at: "2026-03-22T10:00:00",
    },
  ],
  warnings: [],
  updated_at: "2026-03-22T10:00:00",
};


function buildModeAllocations(values = {}) {
  return ALL_MODES.map((modeType) => ({
    mode_type: modeType,
    target_dedicated_count: values[modeType] ?? 0,
  }));
}


function buildRuntimeModes(values = {}) {
  return {
    new_api: {
      mode_type: "new_api",
      target_dedicated_count: 1,
      actual_dedicated_count: 1,
      status: "dedicated",
      status_message: "专属中 1/1",
      shared_available_count: 1,
      ...(values.new_api || {}),
    },
    fast_api: {
      mode_type: "fast_api",
      target_dedicated_count: 0,
      actual_dedicated_count: 0,
      status: "shared",
      status_message: "共享中",
      shared_available_count: 1,
      ...(values.fast_api || {}),
    },
    token: {
      mode_type: "token",
      target_dedicated_count: 0,
      actual_dedicated_count: 0,
      status: "shared",
      status_message: "共享中",
      shared_available_count: 3,
      ...(values.token || {}),
    },
  };
}


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


function buildQueryConfigDetail(configId = "cfg-1", overrides = {}) {
  if (configId === "cfg-2") {
    return {
      config_id: "cfg-2",
      name: "夜刀配置",
      description: "夜间专用",
      enabled: true,
      created_at: "2026-03-20T09:05:00",
      updated_at: "2026-03-20T09:05:00",
      mode_settings: [],
      items: [
        {
          query_item_id: "item-2",
          config_id: "cfg-2",
          product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267002",
          external_item_id: "1380979899390267002",
          item_name: "AWP | Asiimov",
          market_hash_name: "AWP | Asiimov (Field-Tested)",
          min_wear: 0.18,
          max_wear: 1,
          detail_min_wear: 0.18,
          detail_max_wear: 0.45,
          max_price: 999,
          last_market_price: 955.55,
          last_detail_sync_at: "2026-03-20T10:05:00",
          manual_paused: false,
          mode_allocations: buildModeAllocations({ fast_api: 1 }),
          sort_order: 0,
          created_at: "2026-03-20T09:05:00",
          updated_at: "2026-03-20T09:05:00",
        },
      ],
      ...overrides,
    };
  }

  return {
    config_id: "cfg-1",
    name: "白天配置",
    description: "白天轮询",
    enabled: true,
    created_at: "2026-03-20T09:00:00",
    updated_at: "2026-03-20T09:00:00",
    mode_settings: [],
    items: [
      {
        query_item_id: "item-1",
        config_id: "cfg-1",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267001",
        external_item_id: "1380979899390267001",
        item_name: "AK-47 | Redline",
        market_hash_name: "AK-47 | Redline (Field-Tested)",
        min_wear: 0.1,
        max_wear: 0.7,
        detail_min_wear: 0.12,
        detail_max_wear: 0.3,
        max_price: 123.45,
        last_market_price: 118.88,
        last_detail_sync_at: "2026-03-20T10:00:00",
        manual_paused: false,
        mode_allocations: buildModeAllocations({ new_api: 1 }),
        sort_order: 0,
        created_at: "2026-03-20T09:00:00",
        updated_at: "2026-03-20T09:00:00",
      },
      {
        query_item_id: "item-3",
        config_id: "cfg-1",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267003",
        external_item_id: "1380979899390267003",
        item_name: "M4A1-S | Blue Phosphor",
        market_hash_name: "M4A1-S | Blue Phosphor (Factory New)",
        min_wear: 0,
        max_wear: 0.08,
        detail_min_wear: 0,
        detail_max_wear: 0.03,
        max_price: 2888,
        last_market_price: 2555.55,
        last_detail_sync_at: "2026-03-20T10:06:00",
        manual_paused: true,
        mode_allocations: buildModeAllocations({ token: 1 }),
        sort_order: 1,
        created_at: "2026-03-20T09:00:00",
        updated_at: "2026-03-20T09:00:00",
      },
    ],
    ...overrides,
  };
}


function buildCapacitySummary(overrides = {}) {
  return {
    modes: {
      new_api: { mode_type: "new_api", available_account_count: 2 },
      fast_api: { mode_type: "fast_api", available_account_count: 1 },
      token: { mode_type: "token", available_account_count: 3 },
      ...(overrides.modes || {}),
    },
    ...overrides,
  };
}


function buildPurchaseRuntimeStatus(overrides = {}) {
  return {
    running: false,
    message: "未运行",
    started_at: null,
    stopped_at: null,
    queue_size: 2,
    active_account_count: 1,
    total_account_count: 2,
    total_purchased_count: 4,
    runtime_session_id: "run-1",
    active_query_config: null,
    matched_product_count: 3,
    purchase_success_count: 1,
    purchase_failed_count: 2,
    recent_events: [
      {
        occurred_at: "2026-03-20T10:00:00",
        status: "queued",
        message: "命中已进入购买池",
        query_item_name: "AK-47 | Redline",
        product_list: [{ productId: "p-1", price: 123.45, actRebateAmount: 0 }],
        total_price: 123.45,
        total_wear_sum: 0.42,
        source_mode_type: "new_api",
        http_status: 202,
        request_method: "POST",
        request_path: "/purchase-runtime/dispatch",
        raw_status: "queued",
      },
      {
        occurred_at: "2026-03-20T10:00:03",
        status: "not login",
        message: "购买失败 1 件",
        query_item_name: "AK-47 | Redline",
        product_list: [{ productId: "p-2", price: 122.0, actRebateAmount: 0 }],
        total_price: 122.0,
        total_wear_sum: 0.38,
        source_mode_type: "token",
        error: "not login",
        http_status: 401,
        request_method: "POST",
        request_path: "/orders/submit",
        response_text: "not login",
        payload: {
          product_ids: ["p-2"],
        },
      },
    ],
    accounts: [
      {
        account_id: "a1",
        display_name: "购买账号-A",
        purchase_capability_state: "bound",
        purchase_pool_state: "active",
        purchase_disabled: false,
        selected_steam_id: "steam-1",
        selected_inventory_name: "主仓",
        selected_inventory_remaining_capacity: 90,
        selected_inventory_max: 1000,
        last_error: null,
        total_purchased_count: 1,
        submitted_product_count: 3,
        purchase_success_count: 1,
        purchase_failed_count: 2,
      },
      {
        account_id: "a2",
        display_name: "购买账号-B",
        purchase_capability_state: "bound",
        purchase_pool_state: "paused_no_inventory",
        purchase_disabled: true,
        selected_steam_id: "steam-2",
        selected_inventory_name: "备用仓",
        selected_inventory_remaining_capacity: 0,
        selected_inventory_max: 1000,
        last_error: "没有可用仓库",
        total_purchased_count: 3,
        submitted_product_count: 0,
        purchase_success_count: 0,
        purchase_failed_count: 0,
      },
    ],
    item_rows: [
      {
        query_item_id: "item-1",
        item_name: "AK-47 | Redline",
        max_price: 123.45,
        min_wear: 0.1,
        max_wear: 0.7,
        detail_min_wear: 0.12,
        detail_max_wear: 0.3,
        query_execution_count: 7,
        matched_product_count: 3,
        purchase_success_count: 1,
        purchase_failed_count: 2,
        manual_paused: false,
        modes: buildRuntimeModes(),
        source_mode_stats: [
          {
            mode_type: "new_api",
            hit_count: 2,
            last_hit_at: "2026-03-20T10:00:00",
            account_id: "query-a",
            account_display_name: "查询账号A",
          },
          {
            mode_type: "fast_api",
            hit_count: 1,
            last_hit_at: "2026-03-20T10:00:03",
            account_id: "query-b",
            account_display_name: "查询账号B",
          },
        ],
        recent_hit_sources: [
          {
            mode_type: "fast_api",
            hit_count: 1,
            last_hit_at: "2026-03-20T10:00:03",
            account_id: "query-b",
            account_display_name: "查询账号B",
          },
          {
            mode_type: "new_api",
            hit_count: 2,
            last_hit_at: "2026-03-20T10:00:00",
            account_id: "query-a",
            account_display_name: "查询账号A",
          },
        ],
      },
    ],
    ...overrides,
  };
}


function createFetchHarness({
  applyRuntimeResult,
  capacitySummary = buildCapacitySummary(),
  configDetails,
  initialStatus,
  initialPurchaseRuntimeSettings = { per_batch_ip_fanout_limit: 1, updated_at: null },
  initialQuerySettings = QUERY_SETTINGS,
  initialUiPreferences = { selected_config_id: null, updated_at: null },
  queryConfigs = QUERY_CONFIGS,
} = {}) {
  let purchaseRuntimeStatus = initialStatus || buildPurchaseRuntimeStatus();
  let purchaseRuntimeSettings = {
    per_batch_ip_fanout_limit: initialPurchaseRuntimeSettings?.per_batch_ip_fanout_limit ?? 1,
    updated_at: initialPurchaseRuntimeSettings?.updated_at ?? null,
  };
  let querySettings = JSON.parse(JSON.stringify(initialQuerySettings));
  let purchaseUiPreferences = {
    selected_config_id: initialUiPreferences?.selected_config_id ?? null,
    updated_at: initialUiPreferences?.updated_at ?? null,
  };
  const queryConfigDetails = {
    "cfg-1": buildQueryConfigDetail("cfg-1"),
    "cfg-2": buildQueryConfigDetail("cfg-2"),
    ...(configDetails || {}),
  };
  const calls = [];

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
    if (url.pathname === "/purchase-runtime/ui-preferences" && method === "GET") {
      return jsonResponse(purchaseUiPreferences);
    }
    if (url.pathname === "/purchase-runtime/ui-preferences" && method === "PUT") {
      purchaseUiPreferences = {
        selected_config_id: body?.selected_config_id ?? null,
        updated_at: "2026-03-22T11:00:00",
      };
      return jsonResponse(purchaseUiPreferences);
    }
    if (url.pathname === "/runtime-settings/purchase" && method === "GET") {
      return jsonResponse(purchaseRuntimeSettings);
    }
    if (url.pathname === "/runtime-settings/purchase" && method === "PUT") {
      purchaseRuntimeSettings = {
        per_batch_ip_fanout_limit: body?.per_batch_ip_fanout_limit ?? purchaseRuntimeSettings.per_batch_ip_fanout_limit,
        updated_at: "2026-03-29T12:00:00",
      };
      return jsonResponse(purchaseRuntimeSettings);
    }
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(queryConfigs);
    }
    if (url.pathname === "/query-settings" && method === "GET") {
      return jsonResponse(querySettings);
    }
    if (url.pathname === "/query-settings" && method === "PUT") {
      const modes = Array.isArray(body?.modes) ? body.modes : [];
      const hasTokenRisk = modes.some((mode) => (
        mode?.mode_type === "token"
        && (Number(mode?.base_cooldown_min) < 10 || Number(mode?.base_cooldown_max) < 10)
      ));
      querySettings = {
        modes,
        warnings: hasTokenRisk ? ["浏览器查询器基础冷却低于 10 秒，封号风险极高"] : [],
        updated_at: "2026-03-22T11:30:00",
      };
      return jsonResponse(querySettings);
    }
    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse(capacitySummary);
    }
    const queryConfigMatch = url.pathname.match(/^\/query-configs\/([^/]+)$/);
    if (queryConfigMatch && method === "GET") {
      return jsonResponse(queryConfigDetails[queryConfigMatch[1]]);
    }
    if (url.pathname === "/purchase-runtime/status" && method === "GET") {
      return jsonResponse(purchaseRuntimeStatus);
    }
    if (url.pathname === "/purchase-runtime/start" && method === "POST") {
      const nextConfig = queryConfigs.find((config) => config.config_id === body?.config_id) || null;
      purchaseRuntimeStatus = buildPurchaseRuntimeStatus({
        ...purchaseRuntimeStatus,
        running: true,
        message: "运行中",
        started_at: "2026-03-19T14:00:00",
        stopped_at: null,
        active_query_config: nextConfig
          ? {
            config_id: nextConfig.config_id,
            config_name: nextConfig.name,
            state: "running",
            message: "运行中",
          }
          : null,
      });
      return jsonResponse(purchaseRuntimeStatus);
    }
    if (url.pathname === "/purchase-runtime/stop" && method === "POST") {
      purchaseRuntimeStatus = buildPurchaseRuntimeStatus({
        ...purchaseRuntimeStatus,
        running: false,
        message: "未运行",
        started_at: null,
        stopped_at: null,
        active_query_config: null,
      });
      return jsonResponse(purchaseRuntimeStatus);
    }
    const queryItemMatch = url.pathname.match(/^\/query-configs\/([^/]+)\/items\/([^/]+)$/);
    if (queryItemMatch && method === "PATCH") {
      const [, configId, queryItemId] = queryItemMatch;
      const nextDetail = queryConfigDetails[configId];
      const nextItem = nextDetail?.items?.find((item) => item.query_item_id === queryItemId);
      if (!nextItem) {
        return jsonResponse({ detail: "Not found" }, 404);
      }
      const updatedItem = {
        ...nextItem,
        detail_min_wear: body?.detail_min_wear ?? nextItem.detail_min_wear,
        detail_max_wear: body?.detail_max_wear ?? nextItem.detail_max_wear,
        max_price: body?.max_price ?? nextItem.max_price,
        manual_paused: body?.manual_paused ?? nextItem.manual_paused,
        mode_allocations: buildModeAllocations(body?.mode_allocations || {}),
      };
      queryConfigDetails[configId] = {
        ...nextDetail,
        items: nextDetail.items.map((item) => (item.query_item_id === queryItemId ? updatedItem : item)),
      };
      return jsonResponse(updatedItem);
    }
    const applyRuntimeMatch = url.pathname.match(/^\/query-configs\/([^/]+)\/items\/([^/]+)\/apply-runtime$/);
    if (applyRuntimeMatch && method === "POST") {
      const [, configId, queryItemId] = applyRuntimeMatch;
      return jsonResponse({
        status: "applied",
        message: "已保存，并已应用到当前运行配置",
        config_id: configId,
        query_item_id: queryItemId,
        ...(applyRuntimeResult || {}),
      });
    }
    const manualAllocationMatch = url.pathname.match(/^\/query-runtime\/configs\/([^/]+)\/manual-assignments$/);
    if (manualAllocationMatch && method === "PUT") {
      const [, configId] = manualAllocationMatch;
      const nextItems = Array.isArray(body?.items) ? body.items : [];
      const nextItemRows = purchaseRuntimeStatus.item_rows.map((itemRow) => {
        const nextModes = { ...(itemRow.modes || {}) };
        for (const nextItem of nextItems) {
          if (nextItem.query_item_id !== itemRow.query_item_id) {
            continue;
          }
          const modeType = nextItem.mode_type;
          if (!nextModes[modeType]) {
            continue;
          }
          nextModes[modeType] = {
            ...nextModes[modeType],
            actual_dedicated_count: nextItem.target_actual_count,
            status: nextItem.target_actual_count > 0 ? "dedicated" : nextModes[modeType].status,
            status_message: nextItem.target_actual_count > 0
              ? `专属中 ${nextItem.target_actual_count}/${nextModes[modeType].target_dedicated_count}`
              : nextModes[modeType].status_message,
          };
        }
        return {
          ...itemRow,
          modes: nextModes,
        };
      });
      purchaseRuntimeStatus = buildPurchaseRuntimeStatus({
        ...purchaseRuntimeStatus,
        item_rows: nextItemRows,
      });
      return jsonResponse({
        running: true,
        config_id: configId,
        config_name: queryConfigs.find((config) => config.config_id === configId)?.name || "查询配置",
        message: "运行中",
        account_count: 2,
        started_at: "2026-03-20T10:00:00",
        stopped_at: null,
        total_query_count: 7,
        total_found_count: 3,
        modes: {},
        group_rows: [],
        recent_events: [],
        item_rows: nextItemRows,
      });
    }
    const purchaseConfigMatch = url.pathname.match(/^\/accounts\/([^/]+)\/purchase-config$/);
    if (purchaseConfigMatch && method === "PATCH") {
      const accountId = purchaseConfigMatch[1];
      const payload = JSON.parse(options.body ?? "{}");
      purchaseRuntimeStatus = buildPurchaseRuntimeStatus({
        ...purchaseRuntimeStatus,
        accounts: purchaseRuntimeStatus.accounts.map((account) => (
          account.account_id === accountId
            ? {
              ...account,
              purchase_disabled: Boolean(payload.purchase_disabled),
              selected_steam_id: payload.selected_steam_id ?? account.selected_steam_id,
            }
            : account
        )),
      });
      return jsonResponse(purchaseRuntimeStatus);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
    getQueryConfigDetail(configId) {
      return queryConfigDetails[configId];
    },
  };
}


describe("purchase system page", () => {
  it("switches into purchase system page", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    expect(screen.queryByRole("heading", { name: "扫货系统" })).not.toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "扫货运行控制台" })).toBeInTheDocument();
    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });
    expect(within(actionRegion).getByRole("button", { name: "最近事件" })).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "查看账号详情" })).toBeInTheDocument();
  });

  it("renders compact runtime bar with config state, action entry and accumulated purchase summary", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        started_at: "2026-03-19T14:00:00",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("运行中")).toBeInTheDocument();
    expect(within(commandDeck).getByRole("button", { name: "查询设置" })).toBeInTheDocument();
    expect(within(commandDeck).getByRole("button", { name: "切换配置" })).toBeInTheDocument();
    expect(within(commandDeck).getByText("累计购买")).toBeInTheDocument();
    expect(within(commandDeck).getByText("4")).toBeInTheDocument();
    expect(within(commandDeck).queryByText("run-1")).not.toBeInTheDocument();
    expect(within(commandDeck).queryByText("队列中")).not.toBeInTheDocument();
    expect(within(commandDeck).queryByText("购买成功 1")).not.toBeInTheDocument();
    expect(within(commandDeck).queryByText("购买失败 2")).not.toBeInTheDocument();
  });

  it("keeps showing the bound config when purchase runtime is waiting", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "waiting",
          message: "等待购买账号恢复",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });

  it("renders flat item monitor rows and moves diagnostics behind floating actions", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const itemToggle = screen.getByRole("button", { name: "AK-47 | Redline" });
    expect(within(itemToggle).getByText("扫货价 <= 123.45")).toBeInTheDocument();
    expect(within(itemToggle).getByText("磨损 0.12 ~ 0.3")).toBeInTheDocument();
    expect(within(itemToggle).getByText("查询次数")).toBeInTheDocument();
    expect(within(itemToggle).getByText("命中")).toBeInTheDocument();
    expect(within(itemToggle).getByText("成功")).toBeInTheDocument();
    expect(within(itemToggle).getByText("失败")).toBeInTheDocument();
    expect(within(itemToggle).getByText("7")).toBeInTheDocument();
    expect(within(itemToggle).getByText("3")).toBeInTheDocument();
    expect(within(itemToggle).getByText("1")).toBeInTheDocument();
    expect(within(itemToggle).getByText("2")).toBeInTheDocument();
    expect(screen.queryByText("查询次数 7")).not.toBeInTheDocument();
    expect(screen.queryByText("命中 3")).not.toBeInTheDocument();
    expect(screen.queryByText("成功 1")).not.toBeInTheDocument();
    expect(screen.queryByText("失败 2")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "最近事件" })).not.toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "购买账号监控" })).not.toBeInTheDocument();

    await user.click(itemToggle);
    expect(itemToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("命中来源")).toBeInTheDocument();
    expect(screen.getByText("查询分配")).toBeInTheDocument();
    expect(screen.getByText("api查询器")).toBeInTheDocument();
    expect(screen.getByText("命中 2次")).toBeInTheDocument();
    expect(screen.getByText("api高速查询器")).toBeInTheDocument();
    expect(screen.getByText("命中 1次")).toBeInTheDocument();
    expect(screen.queryByText("查询账号A / api查询器")).not.toBeInTheDocument();
    expect(screen.queryByText("查询账号B / api高速查询器")).not.toBeInTheDocument();
    expect(screen.queryByText("后续在这里展示 query worker / mode 来源摘要。")).not.toBeInTheDocument();

    expect(screen.getByRole("region", { name: "购买设置" })).toBeInTheDocument();
  });

  it("shows purchase fanout settings and saves the global per-batch limit", async () => {
    const harness = createFetchHarness({
      initialPurchaseRuntimeSettings: { per_batch_ip_fanout_limit: 1, updated_at: null },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const panel = await screen.findByRole("region", { name: "购买设置" });
    const input = within(panel).getByLabelText("单批次单IP并发购买数");
    expect(input).toHaveValue(1);

    fireEvent.change(input, { target: { value: "4" } });
    await user.click(within(panel).getByRole("button", { name: "保存购买设置" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: { per_batch_ip_fanout_limit: 4 },
            method: "PUT",
            pathname: "/runtime-settings/purchase",
          }),
        ]),
      );
    });
    expect(within(panel).getByLabelText("单批次单IP并发购买数")).toHaveValue(4);
  });

  it("opens recent events and account details as independent floating modals", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });

    await user.click(within(actionRegion).getByRole("button", { name: "最近事件" }));
    const recentEventsDialog = await screen.findByRole("dialog", { name: "最近事件" });
    expect(within(recentEventsDialog).getByText("命中已进入购买池")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("HTTP 202")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("POST /purchase-runtime/dispatch")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("原始状态：queued")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("购买失败 1 件")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("HTTP 401")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("POST /orders/submit")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("错误：not login")).toBeInTheDocument();
    expect(within(recentEventsDialog).getByText("原始返回：not login")).toBeInTheDocument();

    await user.click(within(actionRegion).getByRole("button", { name: "查看账号详情" }));
    const accountDialog = await screen.findByRole("dialog", { name: "查看账号详情" });
    expect(within(accountDialog).getByRole("table", { name: "购买账号监控" })).toBeInTheDocument();

    await user.click(within(recentEventsDialog).getByRole("button", { name: "关闭" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "最近事件" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("dialog", { name: "查看账号详情" })).toBeInTheDocument();
  });

  it("requires selecting a config before starting runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });
    expect(within(commandDeck).getByText("未选择配置")).toBeInTheDocument();
    expect(within(commandDeck).getByRole("button", { name: "选择配置" })).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "开始扫货" })).toBeDisabled();
  });

  it("renders the runtime bar as a compact header inside the item list panel", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        item_rows: [],
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const itemsPanel = screen.getByRole("region", { name: "配置商品列表" });
    expect(within(itemsPanel).getByRole("region", { name: "扫货运行控制台" })).toBeInTheDocument();
    expect(within(itemsPanel).getByText("未选择配置")).toBeInTheDocument();
    expect(within(itemsPanel).getByRole("button", { name: "AK-47 | Redline" })).toBeInTheDocument();
    expect(within(itemsPanel).getByText("展示样例")).toBeInTheDocument();
  });

  it("selects a config from the dialog before starting runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });
    await user.click(within(commandDeck).getByRole("button", { name: "选择配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^夜刀配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "使用该配置" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: { selected_config_id: "cfg-2" },
            method: "PUT",
            pathname: "/purchase-runtime/ui-preferences",
          }),
        ]),
      );
      expect(screen.queryByRole("dialog", { name: "选择查询配置" })).not.toBeInTheDocument();
    });
    expect(within(commandDeck).getByText("夜刀配置")).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "开始扫货" })).not.toBeDisabled();

    await user.click(within(actionRegion).getByRole("button", { name: "开始扫货" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: { config_id: "cfg-2" },
            method: "POST",
            pathname: "/purchase-runtime/start",
          }),
        ]),
      );
    });
    expect(within(actionRegion).getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });

  it("uses the same dialog as a switch-config entry while runtime is running", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        started_at: "2026-03-19T14:00:00",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });
    await user.click(within(commandDeck).getByRole("button", { name: "切换配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^夜刀配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "切换到该配置" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: { config_id: "cfg-2" },
            method: "POST",
            pathname: "/purchase-runtime/start",
          }),
        ]),
      );
    });
    expect(within(commandDeck).getByText("夜刀配置")).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });

  it("edits runtime allocations as local drafts and submits them from the footer", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);

    expect(await screen.findByText("实际 1 / 配置 1")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "浏览器查询器 增加实际分配" })[0]).toBeInTheDocument();
    expect(screen.getByText("专属中 1/1")).toBeInTheDocument();
    expect(screen.getByText(/共享余量 3/)).toBeInTheDocument();

    const submitButton = screen.getByRole("button", { name: "提交更改" });
    expect(submitButton).toBeDisabled();
    await user.click(screen.getAllByRole("button", { name: "浏览器查询器 增加实际分配" })[0]);
    expect(submitButton).not.toBeDisabled();
    expect(
      harness.calls.some((call) => (
        call.method === "PUT" && call.pathname === "/query-runtime/configs/cfg-1/manual-assignments"
      )),
    ).toBe(false);

    await user.click(submitButton);

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PUT",
            pathname: "/query-runtime/configs/cfg-1/manual-assignments",
            body: expect.objectContaining({
              items: expect.arrayContaining([
                expect.objectContaining({
                  query_item_id: "item-1",
                  mode_type: "token",
                  target_actual_count: 1,
                }),
              ]),
            }),
          }),
        ]),
      );
    });
    expect(
      harness.calls.some((call) => (
        call.method === "PATCH" && call.pathname === "/query-configs/cfg-1/items/item-1"
      )),
    ).toBe(false);
    expect(
      harness.calls.some((call) => (
        call.method === "POST" && call.pathname === "/query-configs/cfg-1/items/item-1/apply-runtime"
      )),
    ).toBe(false);
  });

  it("does not allow submitting runtime allocation drafts when the selected config is not running", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        item_rows: [],
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    await user.click(within(commandDeck).getByRole("button", { name: "选择配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^白天配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "使用该配置" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);
    expect(screen.getByRole("button", { name: "提交更改" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "浏览器查询器 增加实际分配" })).toBeDisabled();
    expect(
      harness.calls.some((call) => (
        call.method === "PUT" && call.pathname === "/query-runtime/configs/cfg-1/manual-assignments"
      )),
    ).toBe(false);
  });

  it("prompts before leaving the page and saves runtime drafts when the user confirms", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);
    await user.click(screen.getAllByRole("button", { name: "浏览器查询器 增加实际分配" })[0]);

    await user.click(screen.getByRole("button", { name: "账号中心" }));

    const leaveDialog = await screen.findByRole("dialog", { name: "未保存修改" });
    expect(within(leaveDialog).getByText("当前修改尚未保存，离开前选择保存或直接丢弃。")).toBeInTheDocument();

    await user.click(within(leaveDialog).getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    expect(
      harness.calls.some((call) => (
        call.method === "PUT" && call.pathname === "/query-runtime/configs/cfg-1/manual-assignments"
      )),
    ).toBe(true);
  });

  it("prompts before switching config and discards runtime drafts when the user chooses not to save", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);
    await user.click(screen.getAllByRole("button", { name: "浏览器查询器 增加实际分配" })[0]);

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    await user.click(within(commandDeck).getByRole("button", { name: "切换配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^夜刀配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "切换到该配置" }));

    const leaveDialog = await screen.findByRole("dialog", { name: "未保存修改" });
    await user.click(within(leaveDialog).getByRole("button", { name: "不保存" }));

    await waitFor(() => {
      expect(within(commandDeck).getByText("夜刀配置")).toBeInTheDocument();
    });

    expect(
      harness.calls.some((call) => (
        call.method === "PUT" && call.pathname === "/query-runtime/configs/cfg-1/manual-assignments"
      )),
    ).toBe(false);
    expect(
      harness.calls.some((call) => (
        call.method === "POST" && call.pathname === "/purchase-runtime/start" && call.body?.config_id === "cfg-2"
      )),
    ).toBe(true);
  });

  it("prefers persisted page selection over the active runtime config", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        active_query_config: {
          config_id: "cfg-1",
          config_name: "白天配置",
          state: "running",
          message: "运行中",
        },
      }),
      initialUiPreferences: {
        selected_config_id: "cfg-2",
        updated_at: "2026-03-22T10:00:00",
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    expect(within(commandDeck).getByText("夜刀配置")).toBeInTheDocument();
    expect(within(commandDeck).queryByText("白天配置")).not.toBeInTheDocument();
    expect(within(commandDeck).getByText("运行中")).toBeInTheDocument();
  });

  it("shows unselected state when persisted selection points to a deleted config", async () => {
    const harness = createFetchHarness({
      initialUiPreferences: {
        selected_config_id: "cfg-1",
        updated_at: "2026-03-22T10:00:00",
      },
      queryConfigs: [QUERY_CONFIGS[1]],
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "扫货运行动作" });
    expect(within(commandDeck).getByText("未选择配置")).toBeInTheDocument();
    expect(within(commandDeck).queryByText("白天配置")).not.toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "开始扫货" })).toBeDisabled();
  });

  it("opens query settings, blocks invalid minimums and warns before saving risky token cooldowns", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "扫货系统" }));

    const commandDeck = screen.getByRole("region", { name: "扫货运行控制台" });
    await user.click(within(commandDeck).getByRole("button", { name: "查询设置" }));

    const dialog = await screen.findByRole("dialog", { name: "查询设置" });
    const fastApiMinInput = within(dialog).getByLabelText("fast API 基础冷却最小");
    const tokenMinInput = within(dialog).getByLabelText("浏览器 token 基础冷却最小");
    const newApiItemMinInput = within(dialog).getByLabelText("new API 商品最小冷却");
    const newApiItemStrategySelect = within(dialog).getByLabelText("new API 商品冷却策略");

    expect(newApiItemMinInput).toHaveValue(0.5);
    expect(newApiItemStrategySelect).toHaveValue("divide_by_assigned_count");

    await user.clear(fastApiMinInput);
    await user.type(fastApiMinInput, "0.1");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));

    expect(within(dialog).getByText("fast API 基础冷却不能低于 0.2 秒")).toBeInTheDocument();

    await user.clear(fastApiMinInput);
    await user.type(fastApiMinInput, "0.25");
    await user.clear(newApiItemMinInput);
    await user.type(newApiItemMinInput, "0.75");
    await user.selectOptions(newApiItemStrategySelect, "fixed");
    await user.clear(tokenMinInput);
    await user.type(tokenMinInput, "9");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalledWith("浏览器查询器基础冷却低于 10 秒，封号风险极高。是否仍然保存？");
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "查询设置" })).not.toBeInTheDocument();
    });
    expect(
      harness.calls.some((call) => call.method === "PUT" && call.pathname === "/query-settings"),
    ).toBe(true);
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: "PUT",
          pathname: "/query-settings",
          body: expect.objectContaining({
            modes: expect.arrayContaining([
              expect.objectContaining({
                mode_type: "new_api",
                item_min_cooldown_seconds: 0.75,
                item_min_cooldown_strategy: "fixed",
              }),
            ]),
          }),
        }),
      ]),
    );

    confirmSpy.mockRestore();
  });
});
