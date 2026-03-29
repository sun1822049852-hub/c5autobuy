// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


function buildRows() {
  return [
    {
      account_id: "a-1",
      display_name: "账号 A",
      remark_name: "账号 A",
      c5_nick_name: "Nick A",
      default_name: "默认 A",
      api_key_present: true,
      api_key: "api-a",
      new_api_enabled: false,
      fast_api_enabled: false,
      token_enabled: true,
      browser_proxy_mode: "direct",
      browser_proxy_url: null,
      browser_proxy_display: "39.71.213.149",
      browser_public_ip: "39.71.213.149",
      api_proxy_mode: "direct",
      api_proxy_url: null,
      api_proxy_display: "39.71.213.149",
      api_ip_allow_list: "39.71.213.149",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-1",
      purchase_disabled: false,
      selected_steam_id: "steam-1",
      selected_warehouse_text: "steam-1",
    },
    {
      account_id: "a-2",
      display_name: "账号 B",
      remark_name: "账号 B",
      c5_nick_name: "Nick B",
      default_name: "默认 B",
      api_key_present: false,
      api_key: null,
      new_api_enabled: true,
      fast_api_enabled: true,
      token_enabled: true,
      browser_proxy_mode: "custom",
      browser_proxy_url: "http://127.0.0.1:9000",
      browser_proxy_display: "http://127.0.0.1:9000",
      api_proxy_mode: "custom",
      api_proxy_url: "http://127.0.0.1:9000",
      api_proxy_display: "http://127.0.0.1:9000",
      api_ip_allow_list: null,
      api_public_ip: "127.0.0.1",
      purchase_status_code: "not_logged_in",
      purchase_status_text: "未登录",
      purchase_disabled: false,
      selected_steam_id: null,
      selected_warehouse_text: null,
    },
    {
      account_id: "a-3",
      display_name: "账号 C",
      remark_name: "账号 C",
      c5_nick_name: "Nick C",
      default_name: "默认 C",
      api_key_present: true,
      api_key: "api-c",
      new_api_enabled: true,
      fast_api_enabled: true,
      token_enabled: false,
      browser_proxy_mode: "custom",
      browser_proxy_url: "socks5://127.0.0.1:9900",
      browser_proxy_display: "socks5://127.0.0.1:9900",
      api_proxy_mode: "custom",
      api_proxy_url: "socks5://127.0.0.1:9900",
      api_proxy_display: "socks5://127.0.0.1:9900",
      api_ip_allow_list: "39.71.213.149",
      api_public_ip: "39.71.213.149",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-3",
      purchase_disabled: false,
      selected_steam_id: "steam-3",
      selected_warehouse_text: "steam-3",
    },
  ];
}


function buildInventoryMap() {
  return {
    "a-1": {
      account_id: "a-1",
      display_name: "账号 A",
      selected_steam_id: "steam-1",
      refreshed_at: "2026-03-18T10:00:00",
      auto_refresh_due_at: "2026-03-18T10:05:00",
      auto_refresh_remaining_seconds: 300,
      last_error: null,
      inventories: [
        {
          steamId: "steam-1",
          nickname: "主仓一号",
          inventory_num: 900,
          inventory_max: 1000,
          remaining_capacity: 100,
          is_selected: true,
          is_available: true,
        },
        {
          steamId: "steam-2",
          nickname: "备用仓二号",
          inventory_num: 880,
          inventory_max: 1000,
          remaining_capacity: 120,
          is_selected: false,
          is_available: true,
        },
        {
          steamId: "steam-full",
          nickname: "满仓仓库",
          inventory_num: 1000,
          inventory_max: 1000,
          remaining_capacity: 0,
          is_selected: false,
          is_available: false,
        },
      ],
    },
    "a-3": {
      account_id: "a-3",
      display_name: "账号 C",
      selected_steam_id: null,
      refreshed_at: "2026-03-18T10:00:00",
      last_error: "没有可用仓库",
      inventories: [
        {
          steamId: "steam-full",
          nickname: "满仓仓库",
          inventory_num: 1000,
          inventory_max: 1000,
          remaining_capacity: 0,
          is_selected: false,
          is_available: false,
        },
      ],
    },
  };
}


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


function createFetchHarness() {
  let rows = buildRows();
  const inventoryMap = buildInventoryMap();
  const calls = [];
  const taskPollCounts = new Map();

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
      return jsonResponse(rows);
    }

    if (url.pathname === "/accounts" && method === "POST") {
      const nextAccountId = `a-${rows.length + 1}`;
      const createdRow = {
        account_id: nextAccountId,
        display_name: body.remark_name || `账号 ${nextAccountId}`,
        remark_name: body.remark_name || `账号 ${nextAccountId}`,
        c5_nick_name: null,
        default_name: `默认 ${nextAccountId}`,
        api_key_present: Boolean(body.api_key),
        api_key: body.api_key,
        new_api_enabled: true,
        fast_api_enabled: true,
        token_enabled: true,
        browser_proxy_mode: body.browser_proxy_mode,
        browser_proxy_url: body.browser_proxy_url,
        browser_public_ip: null,
        browser_proxy_display: body.browser_proxy_mode === "direct" ? "未获取IP" : body.browser_proxy_url,
        api_proxy_mode: body.api_proxy_mode,
        api_proxy_url: body.api_proxy_url,
        api_proxy_display: body.api_proxy_mode === "direct" ? "未获取IP" : body.api_proxy_url,
        api_public_ip: null,
        purchase_status_code: "not_logged_in",
        purchase_status_text: "未登录",
        purchase_disabled: false,
        selected_steam_id: null,
        selected_warehouse_text: null,
      };
      rows = [...rows, createdRow];
      return jsonResponse(createdRow, 201);
    }

    const loginMatch = url.pathname.match(/^\/accounts\/([^/]+)\/login$/);
    if (loginMatch && method === "POST") {
      const accountId = loginMatch[1];
      return jsonResponse({
        task_id: `task-login-${accountId}`,
        task_type: "login",
        state: "pending",
        created_at: "2026-03-18T12:00:00",
        updated_at: "2026-03-18T12:00:00",
        events: [
          {
            state: "pending",
            timestamp: "2026-03-18T12:00:00",
            message: "任务已创建",
            payload: null,
          },
        ],
        result: null,
        error: null,
        pending_conflict: null,
      }, 202);
    }

    const taskMatch = url.pathname.match(/^\/tasks\/([^/]+)$/);
    if (taskMatch && method === "GET") {
      const taskId = taskMatch[1];
      const nextPollCount = (taskPollCounts.get(taskId) ?? 0) + 1;
      taskPollCounts.set(taskId, nextPollCount);
      const accountId = taskId.replace(/^task-login-/, "");

      if (nextPollCount === 1) {
        return jsonResponse({
          task_id: taskId,
          task_type: "login",
          state: "running",
          created_at: "2026-03-18T12:00:00",
          updated_at: "2026-03-18T12:00:01",
          events: [
            {
              state: "pending",
              timestamp: "2026-03-18T12:00:00",
              message: "任务已创建",
              payload: null,
            },
            {
              state: "running",
              timestamp: "2026-03-18T12:00:01",
              message: "等待扫码确认",
              payload: null,
            },
          ],
          result: null,
          error: null,
          pending_conflict: null,
        });
      }

      rows = rows.map((row) => (
        row.account_id === accountId
          ? {
            ...row,
            purchase_status_code: "selected_warehouse",
            purchase_status_text: `steam-auto-${accountId}`,
            selected_steam_id: `steam-auto-${accountId}`,
            selected_warehouse_text: `steam-auto-${accountId}`,
          }
          : row
      ));

      return jsonResponse({
        task_id: taskId,
        task_type: "login",
        state: "succeeded",
        created_at: "2026-03-18T12:00:00",
        updated_at: "2026-03-18T12:00:02",
        events: [
          {
            state: "pending",
            timestamp: "2026-03-18T12:00:00",
            message: "任务已创建",
            payload: null,
          },
          {
            state: "running",
            timestamp: "2026-03-18T12:00:01",
            message: "等待扫码确认",
            payload: null,
          },
          {
            state: "succeeded",
            timestamp: "2026-03-18T12:00:02",
            message: "登录完成",
            payload: {
              selected_steam_id: `steam-auto-${accountId}`,
            },
          },
        ],
        result: {
          selected_steam_id: `steam-auto-${accountId}`,
        },
        error: null,
        pending_conflict: null,
      });
    }

    const inventoryMatch = url.pathname.match(/^\/purchase-runtime\/accounts\/([^/]+)\/inventory$/);
    if (inventoryMatch && method === "GET") {
      return jsonResponse(inventoryMap[inventoryMatch[1]]);
    }

    const inventoryRefreshMatch = url.pathname.match(/^\/purchase-runtime\/accounts\/([^/]+)\/inventory\/refresh$/);
    if (inventoryRefreshMatch && method === "POST") {
      const accountId = inventoryRefreshMatch[1];
      inventoryMap[accountId] = {
        ...inventoryMap[accountId],
        refreshed_at: "2026-03-18T10:02:00",
        auto_refresh_due_at: "2026-03-18T10:07:00",
        auto_refresh_remaining_seconds: 300,
        inventories: inventoryMap[accountId].inventories.map((inventory) => (
          inventory.steamId === "steam-1"
            ? {
              ...inventory,
              nickname: "主仓一号",
              inventory_num: 800,
              remaining_capacity: 200,
              is_selected: true,
            }
            : inventory
        )),
      };
      return jsonResponse(inventoryMap[accountId]);
    }

    const purchaseConfigMatch = url.pathname.match(/^\/accounts\/([^/]+)\/purchase-config$/);
    if (purchaseConfigMatch && method === "PATCH") {
      const accountId = purchaseConfigMatch[1];
      rows = rows.map((row) => {
        if (row.account_id !== accountId) {
          return row;
        }

        const nextSelectedText = body.selected_steam_id ?? row.selected_warehouse_text;
        return {
          ...row,
          purchase_disabled: body.purchase_disabled,
          selected_steam_id: body.selected_steam_id,
          selected_warehouse_text: nextSelectedText,
          purchase_status_code: body.purchase_disabled ? "disabled" : "selected_warehouse",
          purchase_status_text: body.purchase_disabled ? "禁用" : nextSelectedText,
        };
      });
      return jsonResponse(rows.find((row) => row.account_id === accountId));
    }

    const accountMatch = url.pathname.match(/^\/accounts\/([^/]+)$/);
    if (accountMatch && method === "PATCH") {
      const accountId = accountMatch[1];
      rows = rows.map((row) => {
        if (row.account_id !== accountId) {
          return row;
        }

        const nextRemarkName = body.remark_name ?? row.remark_name;
        const nextApiKey = Object.prototype.hasOwnProperty.call(body, "api_key") ? body.api_key : row.api_key;
        const nextBrowserProxyMode = body.browser_proxy_mode ?? row.browser_proxy_mode;
        const nextBrowserProxyUrl = Object.prototype.hasOwnProperty.call(body, "browser_proxy_url") ? body.browser_proxy_url : row.browser_proxy_url;
        const nextApiProxyMode = body.api_proxy_mode ?? row.api_proxy_mode;
        const nextApiProxyUrl = Object.prototype.hasOwnProperty.call(body, "api_proxy_url") ? body.api_proxy_url : row.api_proxy_url;

        return {
          ...row,
          display_name: nextRemarkName || row.default_name,
          remark_name: nextRemarkName,
          api_key: nextApiKey,
          api_key_present: Boolean(nextApiKey),
          browser_proxy_mode: nextBrowserProxyMode,
          browser_proxy_url: nextBrowserProxyUrl,
          browser_proxy_display: nextBrowserProxyMode === "direct" ? (row.browser_public_ip || "未获取IP") : nextBrowserProxyUrl,
          api_proxy_mode: nextApiProxyMode,
          api_proxy_url: nextApiProxyUrl,
          api_proxy_display: nextApiProxyMode === "direct" ? (row.api_public_ip || "未获取IP") : nextApiProxyUrl,
        };
      });
      return jsonResponse(rows.find((row) => row.account_id === accountId));
    }

    const syncOpenApiMatch = url.pathname.match(/^\/accounts\/([^/]+)\/open-api\/sync$/);
    if (syncOpenApiMatch && method === "POST") {
      const accountId = syncOpenApiMatch[1];
      rows = rows.map((row) => (
        row.account_id === accountId
          ? {
            ...row,
            api_public_ip: row.api_proxy_mode === "direct" ? "39.71.213.149" : "36.138.220.178",
          }
          : row
      ));
      return jsonResponse(rows.find((row) => row.account_id === accountId));
    }

    const openOpenApiMatch = url.pathname.match(/^\/accounts\/([^/]+)\/open-api\/open$/);
    if (openOpenApiMatch && method === "POST") {
      return jsonResponse({
        launched: true,
        account_id: openOpenApiMatch[1],
      });
    }

    const queryModesMatch = url.pathname.match(/^\/accounts\/([^/]+)\/query-modes$/);
    if (queryModesMatch && method === "PATCH") {
      const accountId = queryModesMatch[1];
      rows = rows.map((row) => (
        row.account_id === accountId
          ? {
            ...row,
            new_api_enabled: Object.prototype.hasOwnProperty.call(body, "api_query_enabled")
              ? body.api_query_enabled
              : row.new_api_enabled,
            fast_api_enabled: Object.prototype.hasOwnProperty.call(body, "api_query_enabled")
              ? body.api_query_enabled
              : row.fast_api_enabled,
            token_enabled: Object.prototype.hasOwnProperty.call(body, "browser_query_enabled")
              ? body.browser_query_enabled
              : row.token_enabled,
            api_query_disabled_reason: body.api_query_enabled === false
              ? body.api_query_disabled_reason
              : (body.api_query_enabled === true ? null : row.api_query_disabled_reason),
            browser_query_disabled_reason: body.browser_query_enabled === false
              ? body.browser_query_disabled_reason
              : (body.browser_query_enabled === true ? null : row.browser_query_disabled_reason),
          }
          : row
      ));
      return jsonResponse(rows.find((row) => row.account_id === accountId));
    }

    const clearCapabilityMatch = url.pathname.match(/^\/accounts\/([^/]+)\/purchase-capability\/clear$/);
    if (clearCapabilityMatch && method === "POST") {
      const accountId = clearCapabilityMatch[1];
      rows = rows.map((row) => (
        row.account_id === accountId
          ? {
            ...row,
            purchase_status_code: "not_logged_in",
            purchase_status_text: "未登录",
          }
          : row
      ));
      return jsonResponse(rows.find((row) => row.account_id === accountId));
    }

    const deleteMatch = url.pathname.match(/^\/accounts\/([^/]+)$/);
    if (deleteMatch && method === "DELETE") {
      rows = rows.filter((row) => row.account_id !== deleteMatch[1]);
      return Promise.resolve({
        ok: true,
        status: 204,
        json: async () => ({}),
        text: async () => "",
      });
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
    setRows(updater) {
      rows = typeof updater === "function" ? updater(rows) : updater;
    },
  };
}


describe("account center editing flows", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("creates a new account from the toolbar button and refreshes the list", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");
    await user.click(screen.getByRole("button", { name: "添加账号" }));

    await screen.findByRole("heading", { name: "添加账号" });
    await user.type(screen.getByLabelText("备注"), "账号 D");
    expect(screen.queryByLabelText("API Key")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(await screen.findByText("账号 D")).toBeInTheDocument();
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: {
            api_key: null,
            browser_proxy_mode: "direct",
            browser_proxy_url: null,
            api_proxy_mode: "direct",
            api_proxy_url: null,
            remark_name: "账号 D",
          },
          method: "POST",
          pathname: "/accounts",
        }),
      ]),
    );
    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(within(logDialog).getByText("已添加账号：账号 D")).toBeInTheDocument();
  });

  it("creates an account and immediately starts login from the create dialog", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");
    await user.click(screen.getByRole("button", { name: "添加账号" }));

    await screen.findByRole("heading", { name: "添加账号" });
    await user.type(screen.getByLabelText("备注"), "账号 D");
    await user.type(screen.getByLabelText("浏览器代理"), "user:pass@127.0.0.1:9200");
    await user.click(screen.getByRole("button", { name: "保存并登录" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              api_key: null,
              browser_proxy_mode: "custom",
              browser_proxy_url: "user:pass@127.0.0.1:9200",
              api_proxy_mode: "custom",
              api_proxy_url: "user:pass@127.0.0.1:9200",
              remark_name: "账号 D",
            },
            method: "POST",
            pathname: "/accounts",
          }),
          expect.objectContaining({
            body: {},
            method: "POST",
            pathname: "/accounts/a-4/login",
          }),
        ]),
      );
    });

    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(await within(logDialog).findByText("登录任务已完成：账号 D")).toBeInTheDocument();
    expect(await within(logDialog).findByText("steam-auto-a-4")).toBeInTheDocument();
  });

  it("updates remark and api key with modal editors", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑昵称 账号 A" }));
    await screen.findByRole("heading", { name: "修改备注" });
    await user.clear(screen.getByLabelText("备注"));
    await user.type(screen.getByLabelText("备注"), "新备注");
    await user.click(screen.getByRole("button", { name: "保存" }));

    expect(await screen.findByText("新备注")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "编辑 API Key 账号 B" }));
    await screen.findByRole("heading", { name: "修改 API Key" });
    await user.type(screen.getByLabelText("API Key"), "api-b-new");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: expect.objectContaining({ remark_name: "新备注" }),
            method: "PATCH",
            pathname: "/accounts/a-1",
          }),
          expect.objectContaining({
            body: expect.objectContaining({ api_key: "api-b-new" }),
            method: "PATCH",
            pathname: "/accounts/a-2",
          }),
        ]),
      );
    });
    expect(screen.queryByRole("heading", { name: "登录配置" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(within(logDialog).getByText("已更新 API Key：账号 B")).toBeInTheDocument();
  });

  it("toggles api query through the dedicated query-modes payload", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 C");

    await user.click(screen.getByRole("button", { name: "切换 API 查询 账号 A" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              api_query_enabled: true,
            },
            method: "PATCH",
            pathname: "/accounts/a-1/query-modes",
          }),
        ]),
      );
    });
  });

  it("disables api query with a manual-disabled reason through the dedicated query-modes payload", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 C");

    await user.click(screen.getByRole("button", { name: "切换 API 查询 账号 C" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              api_query_enabled: false,
              api_query_disabled_reason: "manual_disabled",
            },
            method: "PATCH",
            pathname: "/accounts/a-3/query-modes",
          }),
        ]),
      );
    });
  });

  it("toggles browser query through the dedicated query-modes payload", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 C");

    await user.click(screen.getByRole("button", { name: "切换浏览器查询 账号 C" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              browser_query_enabled: true,
            },
            method: "PATCH",
            pathname: "/accounts/a-3/query-modes",
          }),
        ]),
      );
    });
  });

  it("disables browser query with a manual-disabled reason through the dedicated query-modes payload", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 C");

    await user.click(screen.getByRole("button", { name: "切换浏览器查询 账号 A" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              browser_query_enabled: false,
              browser_query_disabled_reason: "manual_disabled",
            },
            method: "PATCH",
            pathname: "/accounts/a-1/query-modes",
          }),
        ]),
      );
    });
  });

  it("opens login drawer after proxy change and opens purchase drawer from purchase status", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));
    const loginDrawerForB = await screen.findByRole("complementary", { name: "登录配置" });
    expect(within(loginDrawerForB).getByText("账号 B")).toBeInTheDocument();
    await user.click(within(loginDrawerForB).getByRole("button", { name: "关闭" }));

    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 A" }));
    const purchaseDrawer = await screen.findByRole("complementary", { name: "购买配置" });
    expect(within(purchaseDrawer).getByRole("heading", { name: "购买配置" })).toBeInTheDocument();
    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: "GET",
          pathname: "/purchase-runtime/accounts/a-1/inventory",
        }),
      ]),
    );
    expect(within(purchaseDrawer).getByDisplayValue("主仓一号")).toBeInTheDocument();
    expect(within(purchaseDrawer).getByText("主仓一号（当前）")).toBeInTheDocument();
    expect(within(purchaseDrawer).getByText("当前仓库占用 900/1000")).toBeInTheDocument();
    expect(within(purchaseDrawer).getByText("自动刷新剩余时间 05:00")).toBeInTheDocument();
    await user.click(within(purchaseDrawer).getByRole("button", { name: "手动刷新仓库" }));
    await waitFor(() => {
      expect(within(purchaseDrawer).getByText("当前仓库占用 800/1000")).toBeInTheDocument();
    });

    const warehouseSelect = within(purchaseDrawer).getByLabelText("当前仓库");
    expect(within(warehouseSelect).getByRole("option", { name: "满仓仓库（库存已满）" })).toBeDisabled();
    await user.selectOptions(warehouseSelect, "steam-2");
    await user.click(within(purchaseDrawer).getByLabelText("禁用该账号的购买能力"));
    await user.click(within(purchaseDrawer).getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              purchase_disabled: true,
              selected_steam_id: "steam-2",
            },
            method: "PATCH",
            pathname: "/accounts/a-1/purchase-config",
          }),
          expect.objectContaining({
            body: null,
            method: "POST",
            pathname: "/purchase-runtime/accounts/a-1/inventory/refresh",
          }),
        ]),
      );
    });
    const purchaseConfigCall = harness.calls.find((call) => call.pathname === "/accounts/a-1/purchase-config");
    expect(purchaseConfigCall?.body).not.toHaveProperty("disabled");
    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(within(logDialog).getByText("已更新购买配置：账号 A")).toBeInTheDocument();
  });

  it("auto syncs whitelist after api proxy change", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑API IP 账号 A" }));
    await screen.findByRole("heading", { name: "API IP 设置" });
    await user.type(screen.getByLabelText("API代理"), "127.0.0.1:9100");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PATCH",
            pathname: "/accounts/a-1",
            body: expect.objectContaining({
              api_proxy_mode: "custom",
              api_proxy_url: "127.0.0.1:9100",
            }),
          }),
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-1/open-api/sync",
            body: {},
          }),
        ]),
      );
    });
  });

  it("opens the binding page from api ip dialog", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑API IP 账号 A" }));
    const dialog = await screen.findByRole("dialog", { name: "API IP 设置" });
    expect(within(dialog).getByRole("note")).toHaveTextContent("39.71.213.149");
    await user.click(screen.getByRole("button", { name: "添加白名单" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-1/open-api/open",
            body: {},
          }),
        ]),
      );
    });
  });

  it("debounces repeated open binding clicks while the request is still pending", async () => {
    const harness = createFetchHarness();
    const pendingOpenResolvers = [];
    const fetchImpl = vi.fn((input, options = {}) => {
      const url = new URL(input);
      if (url.pathname === "/accounts/a-1/open-api/open") {
        return new Promise((resolve) => {
          pendingOpenResolvers.push(() => resolve(jsonResponse({
            launched: true,
            account_id: "a-1",
          })));
        });
      }
      return harness.fetchImpl(input, options);
    });
    installDesktopApp(fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑API IP 账号 A" }));
    await screen.findByRole("heading", { name: "API IP 设置" });
    const openButton = screen.getByRole("button", { name: "添加白名单" });

    await user.click(openButton);
    await user.click(openButton);

    expect(fetchImpl.mock.calls.filter(([input]) => new URL(input).pathname === "/accounts/a-1/open-api/open")).toHaveLength(1);

    pendingOpenResolvers[0]?.();
    await waitFor(() => {
      expect(openButton).not.toBeDisabled();
    });
  });

  it("refreshes the open api ip dialog when whitelist rows change", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑API IP 账号 A" }));
    const dialog = await screen.findByRole("dialog", { name: "API IP 设置" });
    expect(within(dialog).getByRole("note")).toHaveTextContent("39.71.213.149");

    harness.setRows((currentRows) => currentRows.map((row) => (
      row.account_id === "a-1"
        ? {
          ...row,
          api_ip_allow_list: "36.138.220.178, 39.71.213.149",
        }
        : row
    )));

    await user.click(screen.getByRole("button", { name: "刷新" }));

    await waitFor(() => {
      expect(within(dialog).getByRole("note")).toHaveTextContent("36.138.220.178, 39.71.213.149");
    });
  });

  it("updates browser proxy from the browser ip dialog", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑浏览器 IP 账号 A" }));
    await screen.findByRole("heading", { name: "浏览器代理设置" });
    await user.clear(screen.getByLabelText("浏览器代理"));
    await user.type(screen.getByLabelText("浏览器代理"), "127.0.0.1:9200");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PATCH",
            pathname: "/accounts/a-1",
            body: expect.objectContaining({
              browser_proxy_mode: "custom",
              browser_proxy_url: "127.0.0.1:9200",
            }),
          }),
        ]),
      );
    });
    expect(harness.calls).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: "POST",
          pathname: "/accounts/a-1/open-api/sync",
        }),
      ]),
    );
  });

  it("treats direct in the browser ip dialog as a direct connection", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 B");

    await user.click(screen.getByRole("button", { name: "编辑浏览器 IP 账号 B" }));
    await screen.findByRole("heading", { name: "浏览器代理设置" });
    await user.clear(screen.getByLabelText("浏览器代理"));
    await user.type(screen.getByLabelText("浏览器代理"), "direct");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PATCH",
            pathname: "/accounts/a-2",
            body: expect.objectContaining({
              browser_proxy_mode: "direct",
              browser_proxy_url: null,
            }),
          }),
        ]),
      );
    });
  });

  it("clears login state and starts login after browser proxy changes", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑浏览器 IP 账号 A" }));
    await screen.findByRole("heading", { name: "浏览器代理设置" });
    await user.clear(screen.getByLabelText("浏览器代理"));
    await user.type(screen.getByLabelText("浏览器代理"), "http://127.0.0.1:9300");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PATCH",
            pathname: "/accounts/a-1",
            body: expect.objectContaining({
              browser_proxy_mode: "custom",
              browser_proxy_url: "http://127.0.0.1:9300",
            }),
          }),
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-1/purchase-capability/clear",
            body: {},
          }),
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-1/login",
            body: {},
          }),
        ]),
      );
    });
  });

  it("does not restart login when browser proxy is unchanged", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 B");

    await user.click(screen.getByRole("button", { name: "编辑浏览器 IP 账号 B" }));
    await screen.findByRole("heading", { name: "浏览器代理设置" });
    await user.clear(screen.getByLabelText("浏览器代理"));
    await user.type(screen.getByLabelText("浏览器代理"), "http://127.0.0.1:9000");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: "浏览器代理设置" })).not.toBeInTheDocument();
    });
    expect(harness.calls).not.toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "PATCH",
            pathname: "/accounts/a-2",
          }),
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-2/purchase-capability/clear",
          }),
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-2/login",
          }),
      ]),
    );
  });

  it("deletes an account from the context menu after confirmation", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();
    window.confirm = vi.fn(() => true);

    render(<App />);

    const row = await screen.findByText("账号 C");
    fireEvent.contextMenu(row.closest("tr"));

    await user.click(screen.getByRole("button", { name: "删除账号" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "DELETE",
            pathname: "/accounts/a-3",
          }),
        ]),
      );
    });
    expect(window.confirm).toHaveBeenCalled();
    expect(screen.queryByText("账号 C")).not.toBeInTheDocument();
  });
});
