// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

function installEmbeddedDesktopApp(fetchImpl) {
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:59192",
        runtimeWebSocketUrl: "",
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
            registration_flow_version: 2,
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

  it("keeps the legacy one-screen registration UI when registration_flow_version is not 3", async () => {
    const user = userEvent.setup();
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-03-31T20:00:00.000Z",
          program_access: {
            mode: "remote_entitlement",
            stage: "packaged_release",
            guard_enabled: true,
            message: "请先登录程序会员",
            username: null,
            auth_state: null,
            runtime_state: "stopped",
            grace_expires_at: null,
            last_error_code: "program_auth_required",
            registration_flow_version: 2,
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

    const programAccessEntry = await screen.findByRole("button", { name: "打开程序账号窗口" });
    expect(programAccessEntry).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchImpl).toHaveBeenCalled();
    });

    await user.click(programAccessEntry);
    const registerEntry = await screen.findByRole("button", { name: "注册" });
    await user.click(registerEntry);

    expect(await screen.findByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.getByLabelText("注册验证码")).toBeInTheDocument();
    expect(screen.getByLabelText("注册用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("注册密码")).toBeInTheDocument();
  });

  it("enables the three-step registration UI only when registration_flow_version=3", async () => {
    const user = userEvent.setup();
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-03-31T20:00:00.000Z",
          program_access: {
            mode: "remote_entitlement",
            stage: "packaged_release",
            guard_enabled: true,
            message: "请先登录程序会员",
            username: null,
            auth_state: null,
            runtime_state: "stopped",
            grace_expires_at: null,
            last_error_code: "program_auth_required",
            registration_flow_version: 3,
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

    const programAccessEntry = await screen.findByRole("button", { name: "打开程序账号窗口" });
    await user.click(programAccessEntry);
    const registerEntry = await screen.findByRole("button", { name: "注册" });
    await user.click(registerEntry);

    expect(await screen.findByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();
  });

  it("hydrates embedded backend bootstrap before rendering registration flow gating", async () => {
    const user = userEvent.setup();
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-04-23T13:33:30.000Z",
          program_access: {
            mode: "remote_entitlement",
            stage: "packaged_release",
            guard_enabled: true,
            message: "请先登录程序会员",
            username: null,
            auth_state: null,
            runtime_state: "stopped",
            grace_expires_at: null,
            last_error_code: "program_auth_required",
            registration_flow_version: 3,
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
    installEmbeddedDesktopApp(fetchImpl);

    render(<App />);

    const programAccessEntry = await screen.findByRole("button", { name: "打开程序账号窗口" });
    await waitFor(() => {
      expect(
        fetchImpl.mock.calls.some(([input]) => String(input) === "http://127.0.0.1:59192/app/bootstrap"),
      ).toBe(true);
    });

    await user.click(programAccessEntry);
    const registerEntry = await screen.findByRole("button", { name: "注册" });
    await user.click(registerEntry);

    expect(await screen.findByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();
  });
});
