// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}


function installDesktopApp(fetchImpl, bootstrapOverrides = {}) {
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:8123",
        backendStatus: "ready",
        runtimeWebSocketUrl: "",
        pageWarmupEnabled: false,
        ...bootstrapOverrides,
      };
    },
  };
}


function createFetchHarness() {
  const calls = [];
  const fetchImpl = vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();
    calls.push({
      method,
      pathname: url.pathname,
      search: url.search,
    });

    if (url.pathname === "/app/bootstrap" && method === "GET") {
      return jsonResponse({
        version: 1,
        generated_at: "2026-04-24T08:00:00.000Z",
        program_access: {
          mode: "local_pass_through",
          stage: "prepackaging",
          guard_enabled: false,
          message: "local",
          username: null,
          auth_state: null,
          runtime_state: null,
          grace_expires_at: null,
          last_error_code: null,
          registration_flow_version: 2,
        },
        query_system: {
          configs: [
            {
              config_id: "config-1",
              name: "默认配置",
              description: "背景预热配置",
              enabled: true,
              items: [],
              serverShape: "summary",
            },
          ],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: false, config_id: "config-1", item_rows: [] },
        },
        purchase_system: {
          runtimeStatus: { running: false, accounts: [], item_rows: [] },
          uiPreferences: { selected_config_id: "config-1", updated_at: null },
          runtimeSettings: { per_batch_ip_fanout_limit: 1, max_inflight_per_account: 3 },
        },
      });
    }

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }

    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse([
        {
          config_id: "config-1",
          name: "默认配置",
          description: "背景预热配置",
          enabled: true,
          items: [],
          serverShape: "summary",
        },
      ]);
    }

    if (url.pathname === "/query-configs/config-1" && method === "GET") {
      return jsonResponse({
        config_id: "config-1",
        name: "默认配置",
        description: "背景预热配置",
        enabled: true,
        items: [],
        serverShape: "detail",
      });
    }

    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse({ modes: {} });
    }

    if (url.pathname === "/query-runtime/status" && method === "GET") {
      return jsonResponse({ running: false, config_id: "config-1", item_rows: [] });
    }

    if (url.pathname === "/purchase-runtime/status" && method === "GET") {
      return jsonResponse({ running: false, accounts: [], item_rows: [] });
    }

    if (url.pathname === "/purchase-runtime/ui-preferences" && method === "GET") {
      return jsonResponse({ selected_config_id: "config-1", updated_at: null });
    }

    if (url.pathname === "/runtime-settings/purchase" && method === "GET") {
      return jsonResponse({ per_batch_ip_fanout_limit: 1, max_inflight_per_account: 3 });
    }

    if (url.pathname === "/stats/query-items" && method === "GET") {
      return jsonResponse({
        items: [
          {
            external_item_id: "query-item-1",
            item_name: "AK-47 | Redline",
            query_execution_count: 4,
            matched_product_count: 2,
            purchase_success_count: 1,
            purchase_failed_count: 1,
            source_mode_stats: [],
          },
        ],
      });
    }

    if (url.pathname === "/stats/account-capability" && method === "GET") {
      return jsonResponse({
        items: [
          {
            account_id: "account-1",
            account_display_name: "购买账号-A",
            new_api: { display_text: "182ms · 12次" },
            fast_api: { display_text: "--" },
            browser: { display_text: "340ms · 4次" },
            create_order: { display_text: "520ms · 3次" },
            submit_order: { display_text: "810ms · 3次" },
          },
        ],
      });
    }

    if (url.pathname === "/diagnostics/sidebar" && method === "GET") {
      return jsonResponse({
        summary: {
          query_running: false,
          purchase_running: false,
          active_query_config_name: "",
          last_error: "",
        },
        query: {
          last_error: "",
          account_rows: [],
          recent_events: [],
        },
        purchase: {
          last_error: "",
          account_rows: [],
          recent_events: [],
        },
        login_tasks: {
          recent_tasks: [],
        },
        updated_at: "2026-04-24T08:00:00.000Z",
      });
    }

    if (url.pathname === "/proxy-pool" && method === "GET") {
      return jsonResponse([]);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}${url.search}`);
  });

  return { calls, fetchImpl };
}


function countCalls(calls, pathname) {
  return calls.filter((call) => call.method === "GET" && call.pathname === pathname).length;
}


function countCallsWithSearch(calls, pathname, search = "") {
  return calls.filter((call) => (
    call.method === "GET"
    && call.pathname === pathname
    && call.search === search
  )).length;
}


describe("app page keepalive", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    delete window.desktopApp;
  });

  it("warms account center in the background even when another page is the startup tab", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    window.localStorage.setItem("app-shell-state", JSON.stringify({
      activeItem: "query-stats",
    }));

    render(<App />);

    await screen.findByRole("table", { name: "查询统计表" });

    await waitFor(() => {
      expect(countCalls(harness.calls, "/account-center/accounts")).toBe(1);
    });
  });

  it("does not refetch account center and stats pages when revisiting from the sidebar", async () => {
    const harness = createFetchHarness();
    const user = userEvent.setup();
    installDesktopApp(harness.fetchImpl);

    render(<App />);

    await screen.findByRole("searchbox", { name: "搜索账号" });
    await waitFor(() => {
      expect(countCalls(harness.calls, "/account-center/accounts")).toBe(1);
    });

    await user.click(screen.getByRole("button", { name: "查询统计" }));
    await screen.findByRole("table", { name: "查询统计表" });
    expect(countCalls(harness.calls, "/stats/query-items")).toBe(1);

    await user.click(screen.getByRole("button", { name: "账号能力统计" }));
    await screen.findByRole("table", { name: "账号能力统计表" });
    expect(countCalls(harness.calls, "/stats/account-capability")).toBe(1);

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByRole("searchbox", { name: "搜索账号" });
    expect(countCalls(harness.calls, "/account-center/accounts")).toBe(1);

    await user.click(screen.getByRole("button", { name: "查询统计" }));
    await screen.findByRole("table", { name: "查询统计表" });
    expect(countCalls(harness.calls, "/stats/query-items")).toBe(1);

    await user.click(screen.getByRole("button", { name: "账号能力统计" }));
    await screen.findByRole("table", { name: "账号能力统计表" });
    expect(countCalls(harness.calls, "/stats/account-capability")).toBe(1);
  });

  it("does not immediately refetch diagnostics when reopening the diagnostics page", async () => {
    const harness = createFetchHarness();
    const user = userEvent.setup();
    installDesktopApp(harness.fetchImpl);

    render(<App />);

    await screen.findByRole("searchbox", { name: "搜索账号" });

    await user.click(screen.getByRole("button", { name: "通用诊断" }));
    await screen.findByRole("complementary", { name: "通用诊断面板" });
    expect(countCalls(harness.calls, "/diagnostics/sidebar")).toBe(1);

    await user.click(screen.getByRole("button", { name: "账号中心" }));
    await screen.findByRole("searchbox", { name: "搜索账号" });

    await user.click(screen.getByRole("button", { name: "通用诊断" }));
    await screen.findByRole("complementary", { name: "通用诊断面板" });
    expect(countCalls(harness.calls, "/diagnostics/sidebar")).toBe(1);
  });

  it("warms hidden top-level pages and their first data requests in the background after home becomes interactive", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl, {
      pageWarmupEnabled: true,
    });

    render(<App />);

    await screen.findByRole("searchbox", { name: "搜索账号" });

    await waitFor(() => {
      expect(countCallsWithSearch(harness.calls, "/app/bootstrap", "")).toBe(1);
      expect(countCalls(harness.calls, "/stats/query-items")).toBe(1);
      expect(countCalls(harness.calls, "/stats/account-capability")).toBe(1);
      expect(countCalls(harness.calls, "/diagnostics/sidebar")).toBeGreaterThanOrEqual(1);
      expect(countCalls(harness.calls, "/query-configs")).toBeGreaterThanOrEqual(1);
      expect(countCalls(harness.calls, "/query-configs/config-1")).toBeGreaterThanOrEqual(1);
    });
  });

  it("deduplicates concurrent hidden warmup requests for the same query config payload", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl, {
      pageWarmupEnabled: true,
    });

    render(<App />);

    await screen.findByRole("searchbox", { name: "搜索账号" });

    await waitFor(() => {
      expect(countCalls(harness.calls, "/query-configs")).toBe(1);
      expect(countCalls(harness.calls, "/query-configs/config-1")).toBe(1);
    });
  });
});
