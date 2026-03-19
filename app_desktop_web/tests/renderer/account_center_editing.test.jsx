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
      proxy_mode: "direct",
      proxy_url: null,
      proxy_display: "直连",
      purchase_status_code: "selected_warehouse",
      purchase_status_text: "steam-1",
      disabled: false,
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
      proxy_mode: "custom",
      proxy_url: "http://127.0.0.1:9000",
      proxy_display: "http://127.0.0.1:9000",
      purchase_status_code: "not_logged_in",
      purchase_status_text: "未登录",
      disabled: false,
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
      proxy_mode: "custom",
      proxy_url: "socks5://127.0.0.1:9900",
      proxy_display: "socks5://127.0.0.1:9900",
      purchase_status_code: "inventory_full",
      purchase_status_text: "库存已满",
      disabled: false,
      purchase_disabled: false,
      selected_steam_id: null,
      selected_warehouse_text: null,
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
        proxy_mode: body.proxy_mode,
        proxy_url: body.proxy_url,
        proxy_display: body.proxy_mode === "direct" ? "直连" : body.proxy_url,
        purchase_status_code: "not_logged_in",
        purchase_status_text: "未登录",
        disabled: false,
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
          disabled: body.disabled,
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
        const nextProxyMode = body.proxy_mode ?? row.proxy_mode;
        const nextProxyUrl = Object.prototype.hasOwnProperty.call(body, "proxy_url") ? body.proxy_url : row.proxy_url;

        return {
          ...row,
          display_name: nextRemarkName || row.default_name,
          remark_name: nextRemarkName,
          api_key: nextApiKey,
          api_key_present: Boolean(nextApiKey),
          proxy_mode: nextProxyMode,
          proxy_url: nextProxyUrl,
          proxy_display: nextProxyMode === "direct" ? "直连" : nextProxyUrl,
        };
      });
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
  };
}


describe("account center editing flows", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
            proxy_mode: "direct",
            proxy_url: null,
            remark_name: "账号 D",
          },
          method: "POST",
          pathname: "/accounts",
        }),
      ]),
    );
    expect(screen.getByText("已添加账号：账号 D")).toBeInTheDocument();
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
    await user.type(screen.getByLabelText("代理"), "user:pass@127.0.0.1:9200");
    await user.click(screen.getByRole("button", { name: "保存并登录" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              api_key: null,
              proxy_mode: "custom",
              proxy_url: "user:pass@127.0.0.1:9200",
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

    expect(await screen.findByText("登录任务已完成：账号 D")).toBeInTheDocument();
    expect(await screen.findByText("steam-auto-a-4")).toBeInTheDocument();
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
    expect(screen.getByText("已更新 API Key：账号 B")).toBeInTheDocument();
  });

  it("opens login drawer after proxy change and opens purchase drawer from purchase status", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 A");

    await user.click(screen.getByRole("button", { name: "编辑代理 账号 B" }));
    await screen.findByRole("heading", { name: "修改代理" });
    await user.clear(screen.getByLabelText("代理"));
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: expect.objectContaining({
              proxy_mode: "direct",
              proxy_url: null,
            }),
            method: "PATCH",
            pathname: "/accounts/a-2",
          }),
        ]),
      );
    });

    const loginDrawer = await screen.findByRole("complementary", { name: "登录配置" });
    expect(within(loginDrawer).getByRole("heading", { name: "登录配置" })).toBeInTheDocument();
    expect(within(loginDrawer).getByText("账号 B")).toBeInTheDocument();
    expect(within(loginDrawer).getByText("直连")).toBeInTheDocument();

    await user.click(within(loginDrawer).getByRole("button", { name: "关闭" }));

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
    expect(screen.getByText("已更新购买配置：账号 A")).toBeInTheDocument();
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
