// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
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
      ...(values.new_api || {}),
    },
    fast_api: {
      mode_type: "fast_api",
      target_dedicated_count: 0,
      actual_dedicated_count: 0,
      status: "shared",
      status_message: "共享中",
      ...(values.fast_api || {}),
    },
    token: {
      mode_type: "token",
      target_dedicated_count: 0,
      actual_dedicated_count: 0,
      status: "shared",
      status_message: "共享中",
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
      },
      {
        occurred_at: "2026-03-20T10:00:03",
        status: "purchased",
        message: "购买成功 1 件",
        query_item_name: "AK-47 | Redline",
        product_list: [{ productId: "p-2", price: 122.0, actRebateAmount: 0 }],
        total_price: 122.0,
        total_wear_sum: 0.38,
        source_mode_type: "token",
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
} = {}) {
  let purchaseRuntimeStatus = initialStatus || buildPurchaseRuntimeStatus();
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
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(QUERY_CONFIGS);
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
      const nextConfig = QUERY_CONFIGS.find((config) => config.config_id === body?.config_id) || null;
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

    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    expect(screen.queryByRole("heading", { name: "购买系统" })).not.toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "购买运行控制台" })).toBeInTheDocument();
    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("运行中")).toBeInTheDocument();
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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });

  it("renders flat item monitor rows and moves diagnostics behind floating actions", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const itemToggle = screen.getByRole("button", { name: "AK-47 | Redline" });
    expect(within(itemToggle).getByText("价格 <= 123.45")).toBeInTheDocument();
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

    expect(screen.queryByRole("region", { name: "购买账号启用设置" })).not.toBeInTheDocument();
  });

  it("opens recent events and account details as independent floating modals", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });

    await user.click(within(actionRegion).getByRole("button", { name: "最近事件" }));
    const recentEventsDialog = await screen.findByRole("dialog", { name: "最近事件" });
    expect(within(recentEventsDialog).getByText("命中已进入购买池")).toBeInTheDocument();

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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const itemsPanel = screen.getByRole("region", { name: "配置商品列表" });
    expect(within(itemsPanel).getByRole("region", { name: "购买运行控制台" })).toBeInTheDocument();
    expect(within(itemsPanel).getByText("未选择配置")).toBeInTheDocument();
    expect(within(itemsPanel).getByRole("button", { name: "AK-47 | Redline" })).toBeInTheDocument();
    expect(within(itemsPanel).getByText("展示样例")).toBeInTheDocument();
  });

  it("selects a config from the dialog before starting runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
    await user.click(within(commandDeck).getByRole("button", { name: "选择配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^夜刀配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "使用该配置" }));

    await waitFor(() => {
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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
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

  it("renders purchase drawer allocation inputs with capacity and saves to config before runtime apply", async () => {
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
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);

    expect(await screen.findByLabelText("api查询器 目标分配数")).toHaveValue(1);
    expect(screen.getByLabelText("api高速查询器 目标分配数")).toHaveValue(0);
    expect(screen.getByLabelText("浏览器查询器 目标分配数")).toHaveValue(0);
    expect(screen.getByText("专属中 1/1")).toBeInTheDocument();
    expect(screen.getByText(/还可分配 1/)).toBeInTheDocument();
    expect(screen.getByText(/还可分配 3/)).toBeInTheDocument();

    const tokenInput = screen.getByLabelText("浏览器查询器 目标分配数");
    await user.clear(tokenInput);
    await user.type(tokenInput, "2");
    await user.click(screen.getByRole("button", { name: "保存分配" }));

    await waitFor(() => {
      expect(screen.getByText("已保存，并已应用到当前运行配置")).toBeInTheDocument();
    });

    const patchCallIndex = harness.calls.findIndex((call) => (
      call.method === "PATCH" && call.pathname === "/query-configs/cfg-1/items/item-1"
    ));
    const applyRuntimeIndex = harness.calls.findIndex((call) => (
      call.method === "POST" && call.pathname === "/query-configs/cfg-1/items/item-1/apply-runtime"
    ));
    expect(patchCallIndex).toBeGreaterThan(-1);
    expect(applyRuntimeIndex).toBeGreaterThan(patchCallIndex);
    expect(harness.calls[patchCallIndex]).toEqual(
      expect.objectContaining({
        body: {
          detail_min_wear: 0.12,
          detail_max_wear: 0.3,
          max_price: 123.45,
          manual_paused: false,
          mode_allocations: {
            new_api: 1,
            fast_api: 0,
            token: 2,
          },
        },
      }),
    );
  });

  it("keeps saved allocation and shows inactive runtime feedback when the selected config is not running", async () => {
    const harness = createFetchHarness({
      applyRuntimeResult: {
        status: "skipped_inactive",
        message: "已保存；当前未运行该配置，将在下次启动时生效",
      },
      initialStatus: buildPurchaseRuntimeStatus({
        item_rows: [],
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    await user.click(within(commandDeck).getByRole("button", { name: "选择配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^白天配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "使用该配置" }));

    const itemToggle = await screen.findByRole("button", { name: "AK-47 | Redline" });
    await user.click(itemToggle);
    await user.click(screen.getByRole("button", { name: "保存分配" }));

    await waitFor(() => {
      expect(screen.getByText("已保存；当前未运行该配置，将在下次启动时生效")).toBeInTheDocument();
    });
    expect(
      harness.calls.some((call) => (
        call.method === "POST" && call.pathname === "/query-configs/cfg-1/items/item-1/apply-runtime"
      )),
    ).toBe(true);
  });
});
