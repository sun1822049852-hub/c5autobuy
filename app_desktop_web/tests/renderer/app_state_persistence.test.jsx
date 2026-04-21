// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
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


function createFetchHarness() {
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
  const configDetails = Object.fromEntries(configs.map((config) => [config.config_id, config]));
  const runtimeStatus = buildIdleRuntimeStatus();

  return vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(configs);
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

    const configMatch = url.pathname.match(/^\/query-configs\/([^/]+)$/);
    if (configMatch && method === "GET") {
      return jsonResponse(configDetails[configMatch[1]]);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });
}


describe("app state persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    delete window.desktopApp;
  });

  it("restores the last active page after remounting the renderer", async () => {
    const fetchImpl = createFetchHarness();
    installDesktopApp(fetchImpl);
    const user = userEvent.setup();

    const firstRender = render(<App />);
    await screen.findByText("C5 交易助手");

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();

    firstRender.unmount();
    resetAppShellRuntimeForTests();

    render(<App />);

    expect(await screen.findByRole("heading", { name: "白天配置" })).toBeInTheDocument();
    const reloadNotice = screen.getByRole("status");
    expect(reloadNotice).toHaveTextContent("检测到界面已重新加载");
    expect(reloadNotice).toHaveTextContent("配置管理");
  });

  it("restores the previously selected query config after remounting the renderer", async () => {
    const fetchImpl = createFetchHarness();
    installDesktopApp(fetchImpl);
    const user = userEvent.setup();

    const firstRender = render(<App />);
    await screen.findByText("C5 交易助手");

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    await user.click(within(nav).getByRole("button", { name: /^夜刀配置/ }));
    expect(await screen.findByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();

    firstRender.unmount();
    resetAppShellRuntimeForTests();

    render(<App />);

    expect(await screen.findByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
  });
});
