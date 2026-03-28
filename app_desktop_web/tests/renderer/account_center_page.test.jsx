// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


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


function accountRows() {
  return [
    {
      account_id: "a-1",
      display_name: "账号 A",
      remark_name: "账号 A",
      c5_nick_name: "Nick A",
      default_name: "默认 A",
      api_key_present: true,
      api_query_enabled: true,
      api_query_status_code: "enabled",
      api_query_status_text: "已启用",
      api_query_disable_reason_code: null,
      api_query_disable_reason_text: null,
      browser_query_enabled: true,
      browser_query_status_code: "enabled",
      browser_query_status_text: "已启用",
      browser_query_disable_reason_code: null,
      browser_query_disable_reason_text: null,
      api_key: "api-a",
      browser_proxy_mode: "direct",
      browser_proxy_url: null,
      browser_proxy_display: "39.71.213.149",
      browser_public_ip: "39.71.213.149",
      api_proxy_mode: "direct",
      api_proxy_url: null,
      api_proxy_display: "39.71.213.149",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-1",
    },
    {
      account_id: "a-2",
      display_name: "账号 B",
      remark_name: "账号 B",
      c5_nick_name: "Nick B",
      default_name: "默认 B",
      api_key_present: false,
      api_query_enabled: false,
      api_query_status_code: "disabled",
      api_query_status_text: "已禁用",
      api_query_disable_reason_code: "missing_api_key",
      api_query_disable_reason_text: "未配置",
      browser_query_enabled: false,
      browser_query_status_code: "disabled",
      browser_query_status_text: "已禁用",
      browser_query_disable_reason_code: "not_logged_in",
      browser_query_disable_reason_text: "未登录",
      api_key: null,
      browser_proxy_mode: "custom",
      browser_proxy_url: "http://127.0.0.1:9000",
      browser_proxy_display: "http://127.0.0.1:9000",
      api_proxy_mode: "custom",
      api_proxy_url: "http://127.0.0.1:9000",
      api_proxy_display: "http://127.0.0.1:9000",
      api_public_ip: "127.0.0.1",
      purchase_status_code: "not_logged_in",
      purchase_status_text: "未登录",
    },
    {
      account_id: "a-3",
      display_name: "账号 C",
      remark_name: "账号 C",
      c5_nick_name: "Nick C",
      default_name: "默认 C",
      api_key_present: true,
      api_query_enabled: false,
      api_query_status_code: "disabled",
      api_query_status_text: "已禁用",
      api_query_disable_reason_code: "ip_invalid",
      api_query_disable_reason_text: "IP失效",
      browser_query_enabled: true,
      browser_query_status_code: "enabled",
      browser_query_status_text: "已启用",
      browser_query_disable_reason_code: null,
      browser_query_disable_reason_text: null,
      api_key: "api-c",
      browser_proxy_mode: "custom",
      browser_proxy_url: "socks5://127.0.0.1:9900",
      browser_proxy_display: "socks5://127.0.0.1:9900",
      api_proxy_mode: "custom",
      api_proxy_url: "socks5://127.0.0.1:9900",
      api_proxy_display: "socks5://127.0.0.1:9900",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "inventory_full",
      purchase_status_text: "库存已满",
    },
  ];
}


function queryModeRows() {
  return [
    {
      account_id: "a-1",
      display_name: "账号 A",
      remark_name: "账号 A",
      c5_nick_name: "Nick A",
      default_name: "默认 A",
      api_key_present: true,
      api_query_enabled: true,
      api_query_status_code: "enabled",
      api_query_status_text: "已启用",
      api_query_disable_reason_code: null,
      api_query_disable_reason_text: null,
      browser_query_enabled: true,
      browser_query_status_code: "enabled",
      browser_query_status_text: "已启用",
      browser_query_disable_reason_code: null,
      browser_query_disable_reason_text: null,
      api_key: "api-a",
      browser_proxy_mode: "direct",
      browser_proxy_url: null,
      browser_proxy_display: "39.71.213.149",
      browser_public_ip: "39.71.213.149",
      api_proxy_mode: "direct",
      api_proxy_url: null,
      api_proxy_display: "39.71.213.149",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-1",
    },
    {
      account_id: "a-2",
      display_name: "账号 B",
      remark_name: "账号 B",
      c5_nick_name: "Nick B",
      default_name: "默认 B",
      api_key_present: false,
      api_query_enabled: false,
      api_query_status_code: "disabled",
      api_query_status_text: "已禁用",
      api_query_disable_reason_code: "missing_api_key",
      api_query_disable_reason_text: "未配置",
      browser_query_enabled: false,
      browser_query_status_code: "disabled",
      browser_query_status_text: "已禁用",
      browser_query_disable_reason_code: "not_logged_in",
      browser_query_disable_reason_text: "未登录",
      api_key: null,
      browser_proxy_mode: "custom",
      browser_proxy_url: "http://127.0.0.1:9000",
      browser_proxy_display: "http://127.0.0.1:9000",
      api_proxy_mode: "custom",
      api_proxy_url: "http://127.0.0.1:9000",
      api_proxy_display: "http://127.0.0.1:9000",
      api_public_ip: "127.0.0.1",
      purchase_status_code: "not_logged_in",
      purchase_status_text: "未登录",
    },
    {
      account_id: "a-3",
      display_name: "账号 C",
      remark_name: "账号 C",
      c5_nick_name: "Nick C",
      default_name: "默认 C",
      api_key_present: true,
      api_query_enabled: false,
      api_query_status_code: "disabled",
      api_query_status_text: "已禁用",
      api_query_disable_reason_code: "ip_invalid",
      api_query_disable_reason_text: "IP失效",
      browser_query_enabled: true,
      browser_query_status_code: "enabled",
      browser_query_status_text: "已启用",
      browser_query_disable_reason_code: null,
      browser_query_disable_reason_text: null,
      api_key: "api-c",
      browser_proxy_mode: "custom",
      browser_proxy_url: "socks5://127.0.0.1:9900",
      browser_proxy_display: "socks5://127.0.0.1:9900",
      api_proxy_mode: "custom",
      api_proxy_url: "socks5://127.0.0.1:9900",
      api_proxy_display: "socks5://127.0.0.1:9900",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-3",
    },
    {
      account_id: "a-4",
      display_name: "账号 D",
      remark_name: "账号 D",
      c5_nick_name: "Nick D",
      default_name: "默认 D",
      api_key_present: true,
      api_query_enabled: false,
      api_query_status_code: "disabled",
      api_query_status_text: "已禁用",
      api_query_disable_reason_code: "manual_disabled",
      api_query_disable_reason_text: "手动禁用",
      browser_query_enabled: false,
      browser_query_status_code: "disabled",
      browser_query_status_text: "已禁用",
      browser_query_disable_reason_code: "manual_disabled",
      browser_query_disable_reason_text: "手动禁用",
      api_key: "api-d",
      browser_proxy_mode: "custom",
      browser_proxy_url: "http://127.0.0.1:9010",
      browser_proxy_display: "http://127.0.0.1:9010",
      api_proxy_mode: "custom",
      api_proxy_url: "http://127.0.0.1:9010",
      api_proxy_display: "http://127.0.0.1:9010",
      api_public_ip: "39.71.213.150",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-4",
    },
  ];
}


beforeEach(() => {
  window.localStorage.clear();
});

describe("account center page", () => {
  it("patches only the pushed account row after websocket updates", async () => {
    class FakeWebSocket {
      static instances = [];

      constructor(url) {
        this.url = url;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        FakeWebSocket.instances.push(this);
        queueMicrotask(() => this.onopen?.());
      }

      emit(payload) {
        this.onmessage?.({ data: JSON.stringify(payload) });
      }

      close() {
        this.onclose?.();
      }
    }

    const originalWebSocket = window.WebSocket;
    window.WebSocket = FakeWebSocket;

    const initialRows = accountRows();
    const updatedAccount = {
      ...initialRows[0],
      api_key: "api-a-updated",
      api_public_ip: "8.8.8.8",
      api_proxy_display: "8.8.8.8",
      browser_public_ip: "8.8.8.8",
      browser_proxy_display: "8.8.8.8",
    };
    const fetchImpl = vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return {
          ok: true,
          json: async () => initialRows,
        };
      }

      if (url.pathname === "/accounts/a-1" && method === "GET") {
        return {
          ok: true,
          json: async () => updatedAccount,
        };
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    });

    installDesktopApp(fetchImpl);
    render(<App />);

    await screen.findByText("账号 A");
    expect(screen.getAllByText("39.71.213.149").length).toBeGreaterThan(0);
    expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8123/ws/accounts/updates");
    const listCallsBeforePush = fetchImpl.mock.calls.filter(([input, options = {}]) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();
      return url.pathname === "/account-center/accounts" && method === "GET";
    }).length;

    FakeWebSocket.instances[0].emit({
      account_id: "a-1",
      event: "write_account",
      updated_at: "2026-03-27T20:00:00",
      payload: { api_key: "api-a-updated" },
    });

    await waitFor(() => {
      expect(screen.getAllByText("8.8.8.8").length).toBeGreaterThan(0);
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/accounts/a-1",
      expect.objectContaining({ method: "GET" }),
    );
    const listCallsAfterPush = fetchImpl.mock.calls.filter(([input, options = {}]) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();
      return url.pathname === "/account-center/accounts" && method === "GET";
    }).length;
    expect(listCallsAfterPush).toBe(listCallsBeforePush);

    window.WebSocket = originalWebSocket;
  });

  it("removes the pushed account row after delete_account websocket updates without refetching detail", async () => {
    class FakeWebSocket {
      static instances = [];

      constructor(url) {
        this.url = url;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        FakeWebSocket.instances.push(this);
        queueMicrotask(() => this.onopen?.());
      }

      emit(payload) {
        this.onmessage?.({ data: JSON.stringify(payload) });
      }

      close() {
        this.onclose?.();
      }
    }

    const originalWebSocket = window.WebSocket;
    window.WebSocket = FakeWebSocket;

    const initialRows = accountRows();
    const fetchImpl = vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return {
          ok: true,
          json: async () => initialRows,
        };
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    });

    installDesktopApp(fetchImpl);
    render(<App />);

    await screen.findByText("账号 B");
    FakeWebSocket.instances[0].emit({
      account_id: "a-2",
      event: "delete_account",
      updated_at: "2026-03-29T12:00:00",
      payload: {},
    });

    await waitFor(() => {
      expect(screen.queryByText("账号 B")).not.toBeInTheDocument();
    });
    expect(fetchImpl).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8123/accounts/a-2",
      expect.anything(),
    );

    window.WebSocket = originalWebSocket;
  });

  it("renders shell navigation, overview cards, account table and log entry point", async () => {
    installDesktopApp(
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => accountRows(),
      }),
    );

    render(<App />);

    expect(screen.getByRole("button", { name: "账号中心" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "配置管理" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "扫货系统" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    expect(screen.getByText("ACCOUNT CENTER")).toBeInTheDocument();
    expect(screen.queryByText(/统一管理账号备注/)).not.toBeInTheDocument();
    expect(screen.queryByText("后端状态：ready")).not.toBeInTheDocument();

    expect(screen.getByText("总账号")).toBeInTheDocument();
    expect(screen.getByText("未登录")).toBeInTheDocument();
    expect(screen.getByText("无 API Key")).toBeInTheDocument();
    expect(screen.getByText("可购买")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "日志 3" })).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "C5昵称" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "API 状态" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "浏览器查询" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "购买状态" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "账号代理" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "API代理" })).toBeInTheDocument();
    expect(screen.getAllByText("39.71.213.149").length).toBeGreaterThan(0);

    expect(screen.queryByLabelText("状态带")).not.toBeInTheDocument();
    expect(screen.queryByText("最近登录任务")).not.toBeInTheDocument();
    expect(screen.queryByText("最近错误")).not.toBeInTheDocument();
    expect(screen.queryByText("最近修改")).not.toBeInTheDocument();

    expect(screen.getByText("账号 A")).toBeInTheDocument();
    expect(screen.getByText("账号 B")).toBeInTheDocument();
    expect(screen.getByText("账号 C")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "切换 API 查询 账号 C" })).toHaveTextContent("IP失效");

    const toolbar = screen.getByRole("searchbox", { name: "搜索账号" }).closest(".account-page__toolbar");
    expect(toolbar).toHaveClass("account-page__toolbar--compact");
    expect(screen.getByText("当前聚焦 总账号")).toBeInTheDocument();
    expect(within(toolbar).getByRole("button", { name: "刷新" })).toBeInTheDocument();
    expect(within(toolbar).getByRole("button", { name: "添加账号" })).toBeInTheDocument();

    const overviewGrid = screen.getByLabelText("概览卡片");
    expect(overviewGrid.closest(".account-page__hero-side")).not.toBeNull();
    expect(overviewGrid).toHaveClass("overview-grid--compact-row");

    await userEvent.setup().click(screen.getByRole("button", { name: "日志 3" }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(within(logDialog).getByText("等待接入真实任务流")).toBeInTheDocument();
    expect(within(logDialog).getByText("当前无错误记录")).toBeInTheDocument();
    expect(within(logDialog).getByText("尚未发生配置改动")).toBeInTheDocument();
  });

  it("filters the main list when clicking overview cards", async () => {
    installDesktopApp(
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => accountRows(),
      }),
    );

    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("账号 A")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "未登录 1" }));

    const table = screen.getByRole("table", { name: "账号列表" });
    expect(within(table).getByText("账号 B")).toBeInTheDocument();
    expect(within(table).queryByText("账号 A")).not.toBeInTheDocument();
    expect(within(table).queryByText("账号 C")).not.toBeInTheDocument();
  });

  it("renders api and browser query statuses while keeping the api key edit entry", async () => {
    installDesktopApp(
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => queryModeRows(),
      }),
    );

    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("button", { name: "总账号 4" });
    await user.click(screen.getByRole("button", { name: "总账号 4" }));
    await waitFor(() => {
      expect(screen.getByText("账号 D")).toBeInTheDocument();
    });

    expect(screen.getByRole("columnheader", { name: "API 状态" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "浏览器查询" })).toBeInTheDocument();

    const enabledRow = screen.getByText("账号 A").closest("tr");
    expect(enabledRow).not.toBeNull();
    expect(within(enabledRow).getByRole("button", { name: "切换 API 查询 账号 A" })).toHaveTextContent("已启用");
    expect(within(enabledRow).getByRole("button", { name: "切换浏览器查询 账号 A" })).toHaveTextContent("已启用");

    const missingApiRow = screen.getByText("账号 B").closest("tr");
    expect(missingApiRow).not.toBeNull();
    expect(within(missingApiRow).getByRole("button", { name: "切换 API 查询 账号 B" })).toHaveTextContent("已禁用");
    expect(within(missingApiRow).getByRole("button", { name: "切换 API 查询 账号 B" })).toHaveTextContent("未配置");
    expect(within(missingApiRow).getByRole("button", { name: "切换浏览器查询 账号 B" })).toHaveTextContent("已禁用");
    expect(within(missingApiRow).getByRole("button", { name: "切换浏览器查询 账号 B" })).toHaveTextContent("未登录");

    const ipInvalidRow = screen.getByText("账号 C").closest("tr");
    expect(ipInvalidRow).not.toBeNull();
    expect(within(ipInvalidRow).getByRole("button", { name: "切换 API 查询 账号 C" })).toHaveTextContent("已禁用");
    expect(within(ipInvalidRow).getByRole("button", { name: "切换 API 查询 账号 C" })).toHaveTextContent("IP失效");

    const manualDisabledRow = screen.getByText("账号 D").closest("tr");
    expect(manualDisabledRow).not.toBeNull();
    expect(within(manualDisabledRow).getByRole("button", { name: "切换 API 查询 账号 D" })).toHaveTextContent("已禁用");
    expect(within(manualDisabledRow).getByRole("button", { name: "切换 API 查询 账号 D" })).toHaveTextContent("手动禁用");
    expect(within(manualDisabledRow).getByRole("button", { name: "切换浏览器查询 账号 D" })).toHaveTextContent("已禁用");
    expect(within(manualDisabledRow).getByRole("button", { name: "切换浏览器查询 账号 D" })).toHaveTextContent("手动禁用");
    expect(screen.getByRole("button", { name: "编辑 API Key 账号 D" })).toBeInTheDocument();
  });

  it("keeps chrome copy non-selectable while preserving input selection", async () => {
    installDesktopApp(
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => accountRows(),
      }),
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    const navButton = screen.getByRole("button", { name: "账号中心" });
    const pageTitle = screen.getByText("C5 账号中心");
    const tableHeader = screen.getByRole("columnheader", { name: "C5昵称" });
    const searchbox = screen.getByRole("searchbox", { name: "搜索账号" });

    expect(navButton.style.userSelect).toBe("none");
    expect(pageTitle.closest(".account-page__hero-copy")?.style.userSelect).toBe("none");
    expect(tableHeader.style.userSelect).toBe("none");
    expect(searchbox.style.userSelect).not.toBe("none");
  });
});
