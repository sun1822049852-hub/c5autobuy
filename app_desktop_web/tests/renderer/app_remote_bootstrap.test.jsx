// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { act, render, screen, waitFor } from "@testing-library/react";
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

function hasRequestedUrl(fetchImpl, { origin, pathname }) {
  return fetchImpl.mock.calls.some(([input]) => {
    const url = new URL(String(input));
    return (!origin || url.origin === origin) && url.pathname === pathname;
  });
}

function getDiagnosticCalls(logRendererDiagnosticImpl, type) {
  return logRendererDiagnosticImpl.mock.calls
    .map(([payload]) => payload)
    .filter((payload) => payload?.type === type);
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

function installDeferredEmbeddedDesktopApp(fetchImpl) {
  let bootstrapListener = () => {};
  window.fetch = fetchImpl;
  window.desktopApp = {
    getBootstrapConfig() {
      return {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:8000",
        runtimeWebSocketUrl: "",
        backendStatus: "starting",
      };
    },
    subscribeBootstrapConfig(listener) {
      bootstrapListener = listener;
      return () => {
        bootstrapListener = () => {};
      };
    },
  };

  return {
    emitReadyBootstrap(payload = {}) {
      bootstrapListener({
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:59192",
        runtimeWebSocketUrl: "",
        backendStatus: "ready",
        ...payload,
      });
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

      if (url.pathname === "/proxy-pool") {
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
    const firstRequestUrl = new URL(String(fetchImpl.mock.calls[0][0]));
    expect(firstRequestUrl.origin).toBe("https://api.example.com");
    expect(firstRequestUrl.pathname).toBe("/app/bootstrap");
    expect(programAccessEntry).toBeInTheDocument();
    expect(programAccessEntry).toHaveTextContent("未登录");
    expect(screen.queryByLabelText("程序会员用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();
  });

  it("renders the startup shell first and hydrates remote bootstrap config asynchronously", async () => {
    let resolveBootstrapConfig;
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

      if (url.pathname === "/proxy-pool") {
        return jsonResponse([]);
      }
      throw new Error(`Unhandled request: ${url.pathname}`);
    });
    window.fetch = fetchImpl;
    window.desktopApp = {
      requestBootstrapConfig() {
        return new Promise((resolve) => {
          resolveBootstrapConfig = resolve;
        });
      },
    };

    render(<App />);

    expect(screen.getByText("本地服务启动中")).toBeInTheDocument();
    expect(fetchImpl).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(typeof resolveBootstrapConfig).toBe("function");
    });

    resolveBootstrapConfig({
      backendMode: "remote",
      apiBaseUrl: "https://api.example.com",
      runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
      backendStatus: "ready",
    });

    await waitFor(() => {
      expect(hasRequestedUrl(fetchImpl, {
        origin: "https://api.example.com",
        pathname: "/app/bootstrap",
      })).toBe(true);
    });
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

      if (url.pathname === "/proxy-pool") {
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

      if (url.pathname === "/proxy-pool") {
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

      if (url.pathname === "/proxy-pool") {
        return jsonResponse([]);
      }
      throw new Error(`Unhandled request: ${url.pathname}`);
    });
    installEmbeddedDesktopApp(fetchImpl);

    render(<App />);

    const programAccessEntry = await screen.findByRole("button", { name: "打开程序账号窗口" });
    await waitFor(() => {
      expect(hasRequestedUrl(fetchImpl, {
        origin: "http://127.0.0.1:59192",
        pathname: "/app/bootstrap",
      })).toBe(true);
    });

    await user.click(programAccessEntry);
    const registerEntry = await screen.findByRole("button", { name: "注册" });
    await user.click(registerEntry);

    expect(await screen.findByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();
  });

  it("shows the shell immediately for embedded startup and waits for backend ready before fetching bootstrap and home data", async () => {
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-04-24T09:00:00.000Z",
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

      if (url.pathname === "/proxy-pool") {
        return jsonResponse([]);
      }
      throw new Error(`Unhandled request: ${url.pathname}`);
    });
    const desktopHarness = installDeferredEmbeddedDesktopApp(fetchImpl);

    render(<App />);

    expect(await screen.findByText("本地服务启动中")).toBeInTheDocument();
    expect(fetchImpl).not.toHaveBeenCalled();

    await act(async () => {
      desktopHarness.emitReadyBootstrap();
    });

    await waitFor(() => {
      expect(hasRequestedUrl(fetchImpl, {
        origin: "http://127.0.0.1:59192",
        pathname: "/app/bootstrap",
      })).toBe(true);
    });
    await waitFor(() => {
      expect(fetchImpl.mock.calls.some(([input]) => String(input) === "http://127.0.0.1:59192/account-center/accounts")).toBe(true);
    });
  });

  it("reports home interactive only after the embedded home load settles", async () => {
    const fetchImpl = vi.fn(async (input) => {
      const url = new URL(input);

      if (url.pathname === "/app/bootstrap") {
        return jsonResponse({
          version: 1,
          generated_at: "2026-04-25T09:00:00.000Z",
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
      if (url.pathname === "/proxy-pool") {
        return jsonResponse([]);
      }

      throw new Error(`Unhandled request: ${url.pathname}`);
    });
    const logRendererDiagnostic = vi.fn();
    const desktopHarness = installDeferredEmbeddedDesktopApp(fetchImpl);
    window.desktopApp.logRendererDiagnostic = logRendererDiagnostic;

    render(<App />);

    expect(getDiagnosticCalls(logRendererDiagnostic, "startup_trace_home_interactive")).toEqual([]);

    await act(async () => {
      desktopHarness.emitReadyBootstrap();
    });

    await waitFor(() => {
      expect(hasRequestedUrl(fetchImpl, {
        origin: "http://127.0.0.1:59192",
        pathname: "/app/bootstrap",
      })).toBe(true);
    });
    await waitFor(() => {
      expect(fetchImpl.mock.calls.some(([input]) => String(input) === "http://127.0.0.1:59192/account-center/accounts")).toBe(true);
    });
    await waitFor(() => {
      expect(getDiagnosticCalls(logRendererDiagnostic, "startup_trace_home_interactive")).toHaveLength(1);
    });
  });
});
