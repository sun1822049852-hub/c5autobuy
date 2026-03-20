// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


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
    active_query_config: {
      config_id: "cfg-1",
      config_name: "白天配置",
      state: "running",
      message: "运行中",
    },
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
    calls.push({
      method,
      pathname: url.pathname,
    });

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }
    if (url.pathname === "/purchase-runtime/status" && method === "GET") {
      return jsonResponse(purchaseRuntimeStatus);
    }
    if (url.pathname === "/purchase-runtime/start" && method === "POST") {
      purchaseRuntimeStatus = buildPurchaseRuntimeStatus({
        ...purchaseRuntimeStatus,
        running: true,
        message: "运行中",
        started_at: "2026-03-19T14:00:00",
        stopped_at: null,
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

  it("renders bound config summary, item stats, account stats and runtime action", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: true,
        message: "运行中",
        started_at: "2026-03-19T14:00:00",
      }),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
    expect(screen.getByText("白天配置")).toBeInTheDocument();
    expect(screen.getByText("matched 3")).toBeInTheDocument();
    expect(screen.getByText("success 1")).toBeInTheDocument();
    expect(screen.getByText("failed 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止扫货" })).toBeInTheDocument();

    const itemPanel = screen.getByRole("region", { name: "商品 AK-47 | Redline" });
    expect(within(itemPanel).getByText("查询 7 次")).toBeInTheDocument();
    expect(within(itemPanel).getByText("命中 3")).toBeInTheDocument();
    expect(within(itemPanel).getByText("成功 1")).toBeInTheDocument();
    expect(within(itemPanel).getByText("失败 2")).toBeInTheDocument();

    const accountTable = screen.getByRole("table", { name: "购买账号统计" });
    expect(within(accountTable).getByText("购买账号-A")).toBeInTheDocument();
    expect(within(accountTable).getByText("3")).toBeInTheDocument();
    expect(within(accountTable).getByText("1")).toBeInTheDocument();
    expect(within(accountTable).getByText("2")).toBeInTheDocument();
  });

  it("keeps showing the bound config when purchase runtime is waiting", async () => {
    const harness = createFetchHarness({
      initialStatus: buildPurchaseRuntimeStatus({
        running: false,
        message: "等待购买账号恢复",
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
    expect(screen.getByText("白天配置")).toBeInTheDocument();
    expect(screen.getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始扫货" })).toBeInTheDocument();
  });

  it("renders runtime overview, recent events and account purchase enablement", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    expect(await screen.findByRole("heading", { name: "购买系统" })).toBeInTheDocument();
    const overviewRegion = screen.getByRole("region", { name: "运行总览" });
    expect(overviewRegion).toHaveTextContent("队列中");
    expect(overviewRegion).toHaveTextContent("2");
    expect(overviewRegion).toHaveTextContent("活跃账号");
    expect(overviewRegion).toHaveTextContent("1/2");
    expect(overviewRegion).toHaveTextContent("累计购买");
    expect(overviewRegion).toHaveTextContent("4");
    expect(screen.getByRole("heading", { name: "最近事件" })).toBeInTheDocument();
    expect(screen.getByText("命中已进入购买池")).toBeInTheDocument();
    expect(screen.getByText("购买成功 1 件")).toBeInTheDocument();

    const settingsRegion = screen.getByRole("region", { name: "购买账号启用设置" });
    expect(within(settingsRegion).getByLabelText("购买账号-A")).toBeChecked();
    expect(within(settingsRegion).getByLabelText("购买账号-B")).not.toBeChecked();
    expect(within(settingsRegion).getByRole("button", { name: "保存账号购买配置" })).toBeInTheDocument();
  });

  it("updates account purchase config from the purchase page", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "购买系统" }));

    const settingsRegion = await screen.findByRole("region", { name: "购买账号启用设置" });
    await user.click(within(settingsRegion).getByLabelText("购买账号-B"));
    await user.click(within(settingsRegion).getByRole("button", { name: "保存账号购买配置" }));

    await waitFor(() => {
      expect(
        harness.calls.some((call) => call.pathname === "/accounts/a2/purchase-config" && call.method === "PATCH"),
      ).toBe(true);
    });
    expect(within(settingsRegion).getByLabelText("购买账号-B")).toBeChecked();
  });
});
