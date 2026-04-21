// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";
import { getDesktopBootstrapConfig } from "../../src/desktop/bridge.js";


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


describe("app remote bootstrap", () => {
  afterEach(() => {
    delete window.desktopApp;
  });

  it("adds explicit runtime mode defaults when the desktop bridge is unavailable", () => {
    delete window.desktopApp;

    expect(getDesktopBootstrapConfig()).toEqual({
      apiBaseUrl: "http://127.0.0.1:8000",
      backendMode: "embedded",
      backendStatus: "starting",
      runtimeWebSocketUrl: "",
    });
  });

  it("uses the injected remote api base url during app startup", async () => {
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-03-31T20:00:00.000Z",
          program_access: {
            mode: "local_pass_through",
            stage: "prepackaging",
            guard_enabled: false,
            message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
            username: null,
            auth_state: null,
            runtime_state: null,
            grace_expires_at: null,
            last_error_code: null,
          },
          query_system: {
            configs: [],
            capacitySummary: { modes: {} },
            runtimeStatus: { running: false, item_rows: [] },
          },
          purchase_system: {
            runtimeStatus: { running: false, accounts: [], item_rows: [] },
            uiPreferences: { selected_config_id: null, updated_at: null },
            runtimeSettings: { per_batch_ip_fanout_limit: 1, updated_at: null },
          },
        });
      }
      if (url.pathname === "/account-center/accounts") {
        return jsonResponse([]);
      }

      throw new Error(`Unhandled request: ${url.pathname}`);
    });
    installRemoteDesktopApp(fetchImpl);

    render(<App />);

    await waitFor(() => {
      expect(fetchImpl).toHaveBeenCalled();
    });
    const programAccessEntry = await screen.findByRole("button", { name: "打开程序账号窗口" });
    expect(String(fetchImpl.mock.calls[0][0])).toBe("https://api.example.com/app/bootstrap");
    expect(programAccessEntry).toBeInTheDocument();
    expect(programAccessEntry).toHaveTextContent("未登录");
    expect(screen.queryByLabelText("程序会员用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();
  });
});
