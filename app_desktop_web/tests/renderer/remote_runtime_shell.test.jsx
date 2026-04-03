// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";
import { resetAppShellRuntimeForTests } from "../../src/features/shell/app_shell_state.js";


function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}


function installRemoteDesktopApp(fetchImpl) {
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        backendMode: "remote",
        apiBaseUrl: "https://api.example.com",
        runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
        backendStatus: "ready",
      };
    },
  };
}


function createFetchHarness() {
  const calls = [];
  const queryConfigs = [
    {
      config_id: "cfg-1",
      name: "白天配置",
      description: "白天轮询",
      enabled: true,
      created_at: "2026-03-31T09:00:00",
      updated_at: "2026-03-31T09:00:00",
      items: [],
      mode_settings: [],
    },
  ];
  const queryConfigDetail = {
    config_id: "cfg-1",
    name: "白天配置",
    description: "白天轮询",
    enabled: true,
    created_at: "2026-03-31T09:00:00",
    updated_at: "2026-03-31T09:00:00",
    items: [],
    mode_settings: [],
  };

  const fetchImpl = vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();

    calls.push({
      method,
      pathname: url.pathname,
    });

    if (url.pathname === "/app/bootstrap" && method === "GET") {
      return jsonResponse({
        version: 5,
        generated_at: "2026-03-31T20:00:00.000Z",
        query_system: {
          configs: queryConfigs,
          capacitySummary: {
            modes: {
              new_api: { mode_type: "new_api", available_account_count: 2 },
              fast_api: { mode_type: "fast_api", available_account_count: 1 },
              token: { mode_type: "token", available_account_count: 3 },
            },
          },
          runtimeStatus: {
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
          },
        },
        purchase_system: {
          runtimeStatus: {
            running: false,
            message: "未运行",
            started_at: null,
            stopped_at: null,
            queue_size: 0,
            active_account_count: 0,
            total_account_count: 0,
            total_purchased_count: 0,
            runtime_session_id: "run-1",
            active_query_config: null,
            matched_product_count: 0,
            purchase_success_count: 0,
            purchase_failed_count: 0,
            recent_events: [],
            accounts: [],
            item_rows: [],
          },
          uiPreferences: {
            selected_config_id: null,
            updated_at: null,
          },
          runtimeSettings: {
            per_batch_ip_fanout_limit: 1,
            updated_at: null,
          },
        },
      });
    }
    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(queryConfigs);
    }
    if (url.pathname === "/query-configs/cfg-1" && method === "GET") {
      return jsonResponse(queryConfigDetail);
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
      return jsonResponse({
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
      });
    }
    if (url.pathname === "/purchase-runtime/status" && method === "GET") {
      return jsonResponse({
        running: false,
        message: "未运行",
        started_at: null,
        stopped_at: null,
        queue_size: 0,
        active_account_count: 0,
        total_account_count: 0,
        total_purchased_count: 0,
        runtime_session_id: "run-1",
        active_query_config: null,
        matched_product_count: 0,
        purchase_success_count: 0,
        purchase_failed_count: 0,
        recent_events: [],
        accounts: [],
        item_rows: [],
      });
    }
    if (url.pathname === "/purchase-runtime/ui-preferences" && method === "GET") {
      return jsonResponse({
        selected_config_id: null,
        updated_at: null,
      });
    }
    if (url.pathname === "/runtime-settings/purchase" && method === "GET") {
      return jsonResponse({
        per_batch_ip_fanout_limit: 1,
        updated_at: null,
      });
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
  };
}


describe("remote runtime shell keep alive", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    resetAppShellRuntimeForTests();
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    resetAppShellRuntimeForTests();
    delete window.desktopApp;
  });

  it("keeps query and purchase local dialog state after tab switches", { timeout: 10000 }, async () => {
    const harness = createFetchHarness();
    installRemoteDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("C5 账号中心");
    expect(
      harness.calls.some((call) => call.pathname === "/purchase-runtime/status"),
    ).toBe(false);

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    await user.click(screen.getByRole("button", { name: "新建配置" }));

    const createConfigDialog = await screen.findByRole("dialog", { name: "新建配置" });
    await user.type(within(createConfigDialog).getByLabelText("配置名称"), "alpha");

    expect(
      harness.calls.some((call) => call.pathname === "/purchase-runtime/status"),
    ).toBe(false);

    await user.click(screen.getByRole("button", { name: "扫货系统" }));

    await waitFor(() => {
      expect(
        harness.calls.some((call) => call.pathname === "/purchase-runtime/status"),
      ).toBe(true);
    });

    const runtimeDeck = await screen.findByRole("region", { name: "扫货运行控制台" });
    await user.click(within(runtimeDeck).getByRole("button", { name: "购买设置" }));

    const purchaseSettingsDialog = await screen.findByRole("dialog", { name: "购买设置" });
    const fanoutLimitInput = within(purchaseSettingsDialog).getByLabelText("单批次单IP并发购买数");
    fireEvent.change(fanoutLimitInput, { target: { value: "3" } });

    await user.click(screen.getByRole("button", { name: "配置管理" }));

    const restoredCreateDialog = await screen.findByRole("dialog", { name: "新建配置" });
    expect(within(restoredCreateDialog).getByLabelText("配置名称")).toHaveValue("alpha");

    await user.click(screen.getByRole("button", { name: "扫货系统" }));

    const restoredPurchaseDialog = await screen.findByRole("dialog", { name: "购买设置" });
    expect(within(restoredPurchaseDialog).getByLabelText("单批次单IP并发购买数")).toHaveValue(3);
  });
});
