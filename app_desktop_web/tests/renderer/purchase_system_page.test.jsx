// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


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
      },
    ],
    ...overrides,
  };
}


function createFetchHarness({ initialStatus } = {}) {
  let purchaseRuntimeStatus = initialStatus || buildPurchaseRuntimeStatus();
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
  };
}


describe("purchase system page", () => {
  it("switches into purchase system page", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
  });

  it("renders runtime command deck with bound config, runtime state and runtime session id", async () => {
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

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("运行中")).toBeInTheDocument();
    expect(within(commandDeck).getByText("run-1")).toBeInTheDocument();
    expect(within(commandDeck).getByText("队列中")).toBeInTheDocument();
    expect(within(commandDeck).getByText("2")).toBeInTheDocument();
    expect(within(commandDeck).getByText("真实命中 3")).toBeInTheDocument();
    expect(within(commandDeck).getByText("购买成功 1")).toBeInTheDocument();
    expect(within(commandDeck).getByText("购买失败 2")).toBeInTheDocument();
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

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
    const commandDeck = screen.getByRole("region", { name: "购买运行控制台" });
    expect(within(commandDeck).getByText("白天配置")).toBeInTheDocument();
    expect(within(commandDeck).getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });

  it("renders item accordion, account monitor, recent events and removes runtime whitelist editor", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
    const itemToggle = screen.getByRole("button", { name: "AK-47 | Redline" });
    expect(itemToggle).toHaveAttribute("aria-expanded", "false");
    await user.click(itemToggle);
    expect(itemToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("价格阈值 123.45")).toBeInTheDocument();
    expect(screen.getByText("磨损 0.12 ~ 0.3")).toBeInTheDocument();
    expect(screen.getByText("查询 7")).toBeInTheDocument();
    expect(screen.getByText("命中 3")).toBeInTheDocument();
    expect(screen.getByText("成功 1")).toBeInTheDocument();
    expect(screen.getByText("失败 2")).toBeInTheDocument();

    const accountTable = screen.getByRole("table", { name: "购买账号监控" });
    expect(within(accountTable).getByText("购买账号-A")).toBeInTheDocument();
    expect(within(accountTable).getByText("主仓")).toBeInTheDocument();
    expect(within(accountTable).getByText("910/1000")).toBeInTheDocument();
    expect(within(accountTable).getByText("备用仓")).toBeInTheDocument();
    expect(within(accountTable).getByText("1000/1000")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "最近事件" })).toBeInTheDocument();
    expect(screen.getByText("命中已进入购买池")).toBeInTheDocument();
    expect(screen.getByText("购买成功 1 件")).toBeInTheDocument();

    expect(screen.queryByRole("region", { name: "购买账号启用设置" })).not.toBeInTheDocument();
  });

  it("requires selecting a config before starting runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
    expect(within(actionRegion).getByText("未选择配置")).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "选择配置" })).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "开始扫货" })).toBeDisabled();
  });

  it("selects a config from the dialog before starting runtime", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
    await user.click(within(actionRegion).getByRole("button", { name: "选择配置" }));

    const dialog = await screen.findByRole("dialog", { name: "选择查询配置" });
    await user.click(within(dialog).getByRole("button", { name: /^夜刀配置/ }));
    await user.click(within(dialog).getByRole("button", { name: "使用该配置" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "选择查询配置" })).not.toBeInTheDocument();
    });
    expect(within(actionRegion).getByText("夜刀配置")).toBeInTheDocument();
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

    const actionRegion = screen.getByRole("region", { name: "购买运行动作" });
    await user.click(within(actionRegion).getByRole("button", { name: "切换配置" }));

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
    expect(within(actionRegion).getByText("夜刀配置")).toBeInTheDocument();
    expect(within(actionRegion).getByRole("button", { name: "停止扫货" })).toBeInTheDocument();
  });
});
