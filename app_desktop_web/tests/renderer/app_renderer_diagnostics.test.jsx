// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
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


function installDesktopApp(fetchImpl, logRendererDiagnostic = vi.fn()) {
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        apiBaseUrl: "http://127.0.0.1:8123",
        backendStatus: "ready",
      };
    },
    logRendererDiagnostic,
  };
  return logRendererDiagnostic;
}


function createFetchHarness() {
  const runtimeStatus = {
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
  ];

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
    if (url.pathname === "/query-configs/cfg-1" && method === "GET") {
      return jsonResponse(configs[0]);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });
}


describe("app renderer diagnostics", () => {
  it("logs navigation changes through the desktop bridge", async () => {
    const fetchImpl = createFetchHarness();
    const logRendererDiagnostic = installDesktopApp(fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await screen.findByText("C5 账号中心");

    await waitFor(() => {
      expect(logRendererDiagnostic).toHaveBeenCalledWith(expect.objectContaining({
        type: "renderer_navigation_state",
        details: expect.objectContaining({
          activeItem: "account-center",
        }),
      }));
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    await screen.findByRole("heading", { name: "白天配置" });

    await waitFor(() => {
      expect(logRendererDiagnostic).toHaveBeenCalledWith(expect.objectContaining({
        type: "renderer_navigation_state",
        details: expect.objectContaining({
          activeItem: "query-system",
        }),
      }));
    });
  });

  it("logs window errors and unhandled rejections through the desktop bridge", async () => {
    const fetchImpl = createFetchHarness();
    const logRendererDiagnostic = installDesktopApp(fetchImpl);

    render(<App />);
    await screen.findByText("C5 账号中心");

    const windowError = new Error("renderer exploded");
    window.dispatchEvent(new ErrorEvent("error", {
      message: windowError.message,
      error: windowError,
      filename: "App.jsx",
      lineno: 12,
      colno: 34,
    }));

    const rejectionEvent = new Event("unhandledrejection");
    Object.defineProperty(rejectionEvent, "reason", {
      configurable: true,
      value: new Error("async exploded"),
    });
    window.dispatchEvent(rejectionEvent);

    await waitFor(() => {
      expect(logRendererDiagnostic).toHaveBeenCalledWith(expect.objectContaining({
        type: "renderer_window_error",
        details: expect.objectContaining({
          message: "renderer exploded",
          filename: "App.jsx",
          lineno: 12,
          colno: 34,
        }),
      }));
      expect(logRendererDiagnostic).toHaveBeenCalledWith(expect.objectContaining({
        type: "renderer_unhandled_rejection",
        details: expect.objectContaining({
          reason: expect.objectContaining({
            message: "async exploded",
          }),
        }),
      }));
    });
  });
});
