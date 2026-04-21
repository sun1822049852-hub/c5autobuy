// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


function createDeferred() {
  let resolve;
  let reject;

  const promise = new Promise((nextResolve, nextReject) => {
    resolve = nextResolve;
    reject = nextReject;
  });

  return {
    promise,
    reject,
    resolve,
  };
}


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
      purchase_disabled: false,
      selected_steam_id: null,
      selected_warehouse_text: null,
    },
  ];
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
  let taskPollCount = 0;
  const calls = [];

  const fetchImpl = vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();

    calls.push({
      method,
      pathname: url.pathname,
    });

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse(rows);
    }

    if (url.pathname === "/accounts/a-2/login" && method === "POST") {
      return jsonResponse({
        task_id: "task-login-1",
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

    if (url.pathname === "/tasks/task-login-1" && method === "GET") {
      taskPollCount += 1;

      if (taskPollCount === 1) {
        return jsonResponse({
          task_id: "task-login-1",
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
        row.account_id === "a-2"
          ? {
            ...row,
            api_key_present: true,
            api_key: "api-b",
            purchase_status_code: "selected_warehouse",
            purchase_status_text: "steam-auto",
            selected_steam_id: "steam-auto",
            selected_warehouse_text: "steam-auto",
          }
          : row
      ));

      return jsonResponse({
        task_id: "task-login-1",
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
              selected_steam_id: "steam-auto",
            },
          },
        ],
        result: {
          selected_steam_id: "steam-auto",
        },
        error: null,
        pending_conflict: null,
      });
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
  };
}


describe("login drawer", () => {
  it("starts login, streams task progress, updates account logs and refreshes account rows", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 B");

    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    expect(within(drawer).getByText("账号 B")).toBeInTheDocument();

    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "POST",
            pathname: "/accounts/a-2/login",
          }),
          expect.objectContaining({
            method: "GET",
            pathname: "/tasks/task-login-1",
          }),
        ]),
      );
    });

    expect((await within(drawer).findAllByText("登录完成")).length).toBeGreaterThan(0);
    const statusCard = within(drawer).getByText("任务状态").closest(".drawer-card");
    expect(statusCard).not.toBeNull();
    expect(within(statusCard).getByText("登录完成")).toBeInTheDocument();
    expect(within(drawer).getByText("登录会打开浏览器，请按页面提示完成扫码。")).toBeInTheDocument();
    expect(within(drawer).queryByText("这一版先把账号与代理上下文拉起来，任务状态下一阶段接入。")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(await within(logDialog).findByText("登录任务已完成：账号 B")).toBeInTheDocument();
    expect(within(logDialog).getByText("状态：登录完成")).toBeInTheDocument();
    expect(await within(logDialog).findByText("steam-auto")).toBeInTheDocument();
  });

  it("localizes raw login task states in the drawer when the backend does not provide messages", async () => {
    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return jsonResponse(buildRows());
      }

      if (url.pathname === "/accounts/a-2/login" && method === "POST") {
        return jsonResponse({
          task_id: "task-login-2",
          task_type: "login",
          state: "pending",
          created_at: "2026-03-18T12:10:00",
          updated_at: "2026-03-18T12:10:00",
          events: [
            {
              state: "pending",
              timestamp: "2026-03-18T12:10:00",
              message: null,
              payload: null,
            },
          ],
          result: null,
          error: null,
          pending_conflict: null,
        }, 202);
      }

      if (url.pathname === "/tasks/task-login-2" && method === "GET") {
        return jsonResponse({
          task_id: "task-login-2",
          task_type: "login",
          state: "waiting_for_browser_close",
          created_at: "2026-03-18T12:10:00",
          updated_at: "2026-03-18T12:10:03",
          events: [
            {
              state: "pending",
              timestamp: "2026-03-18T12:10:00",
              message: null,
              payload: null,
            },
            {
              state: "starting_browser",
              timestamp: "2026-03-18T12:10:01",
              message: null,
              payload: null,
            },
            {
              state: "waiting_for_scan",
              timestamp: "2026-03-18T12:10:02",
              message: null,
              payload: null,
            },
            {
              state: "waiting_for_browser_close",
              timestamp: "2026-03-18T12:10:03",
              message: null,
              payload: null,
            },
          ],
          result: null,
          error: null,
          pending_conflict: null,
        });
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    }));

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("账号 B");
    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    expect((await within(drawer).findAllByText("等待关闭登录窗口")).length).toBeGreaterThan(0);
    expect(within(drawer).getByText("已创建")).toBeInTheDocument();
    expect(within(drawer).getByText("正在启动浏览器")).toBeInTheDocument();
    expect(within(drawer).getByText("等待扫码")).toBeInTheDocument();
    expect(within(drawer).queryByText("pending")).not.toBeInTheDocument();
    expect(within(drawer).queryByText("starting_browser")).not.toBeInTheDocument();
    expect(within(drawer).queryByText("waiting_for_scan")).not.toBeInTheDocument();
    expect(within(drawer).queryByText("waiting_for_browser_close")).not.toBeInTheDocument();
  });

  it("keeps raw http error details in logs when login start returns an unhandled string", async () => {
    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return jsonResponse(buildRows());
      }

      if (url.pathname === "/accounts/a-2/login" && method === "POST") {
        return {
          ok: false,
          status: 401,
          text: async () => "not login",
        };
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    }));

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("账号 B");
    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    await user.click(screen.getByRole("button", { name: /^日志 \d+$/ }));
    const logDialog = await screen.findByRole("dialog", { name: "日志" });
    expect(await within(logDialog).findByText("发起登录失败：not login")).toBeInTheDocument();
    expect(within(logDialog).getByText("HTTP 401")).toBeInTheDocument();
    expect(within(logDialog).getByText("POST /accounts/a-2/login")).toBeInTheDocument();
    expect(within(logDialog).getByText("原始返回：not login")).toBeInTheDocument();
  });

  it("treats success as a terminal alias and still refreshes the account row", async () => {
    let taskPollCount = 0;
    let accountListCallCount = 0;
    let rows = buildRows();

    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        accountListCallCount += 1;
        return jsonResponse(rows);
      }

      if (url.pathname === "/accounts/a-2/login" && method === "POST") {
        return jsonResponse({
          task_id: "task-login-1",
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

      if (url.pathname === "/tasks/task-login-1" && method === "GET") {
        taskPollCount += 1;
        rows = rows.map((row) => (
          row.account_id === "a-2"
            ? {
              ...row,
              api_key_present: true,
              api_key: "api-b",
              purchase_status_code: "selected_warehouse",
              purchase_status_text: "steam-auto",
              selected_steam_id: "steam-auto",
              selected_warehouse_text: "steam-auto",
            }
            : row
        ));

        return jsonResponse({
          task_id: "task-login-1",
          task_type: "login",
          state: "success",
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
              state: "success",
              timestamp: "2026-03-18T12:00:02",
              message: "登录完成",
              payload: {
                selected_steam_id: "steam-auto",
              },
            },
          ],
          result: {
            selected_steam_id: "steam-auto",
          },
          error: null,
          pending_conflict: null,
        });
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    }));

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("账号 B");
    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    expect((await within(drawer).findAllByText("登录完成")).length).toBeGreaterThan(0);
    expect(await screen.findByText("steam-auto")).toBeInTheDocument();
    expect(taskPollCount).toBe(1);
    expect(accountListCallCount).toBeGreaterThanOrEqual(2);
  });

  it("stays closed when the user dismisses it while terminal refresh is still in flight", async () => {
    const updatedRows = buildRows().map((row) => (
      row.account_id === "a-2"
        ? {
          ...row,
          api_key_present: true,
          api_key: "api-b",
          purchase_status_code: "selected_warehouse",
          purchase_status_text: "steam-auto",
          selected_steam_id: "steam-auto",
          selected_warehouse_text: "steam-auto",
        }
        : row
    ));
    const refreshDeferred = createDeferred();
    let taskPollCount = 0;
    let accountListCallCount = 0;

    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        accountListCallCount += 1;

        if (accountListCallCount === 1) {
          return jsonResponse(buildRows());
        }

        return refreshDeferred.promise;
      }

      if (url.pathname === "/accounts/a-2/login" && method === "POST") {
        return jsonResponse({
          task_id: "task-login-1",
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

      if (url.pathname === "/tasks/task-login-1" && method === "GET") {
        taskPollCount += 1;

        if (taskPollCount === 1) {
          return jsonResponse({
            task_id: "task-login-1",
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
                state: "succeeded",
                timestamp: "2026-03-18T12:00:02",
                message: "登录完成",
                payload: {
                  selected_steam_id: "steam-auto",
                },
              },
            ],
            result: {
              selected_steam_id: "steam-auto",
            },
            error: null,
            pending_conflict: null,
          });
        }
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    }));

    const user = userEvent.setup();

    render(<App />);

    await screen.findByText("账号 B");
    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    expect((await within(drawer).findAllByText("登录完成")).length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(accountListCallCount).toBe(2);
    });

    await user.click(screen.getByRole("button", { name: "关闭" }));

    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: "登录配置" })).not.toBeInTheDocument();
    });

    refreshDeferred.resolve(jsonResponse(updatedRows));

    expect(await screen.findByText("steam-auto")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByRole("complementary", { name: "登录配置" })).not.toBeInTheDocument();
    });
  });

  it("allows login without touching removed browser-environment diagnostics routes", async () => {
    const calls = [];

    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();
      calls.push({ method, pathname: url.pathname });

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return jsonResponse(buildRows());
      }

      if (url.pathname === "/accounts/a-2/login" && method === "POST") {
        return jsonResponse({
          task_id: "task-login-1",
          task_type: "login",
          state: "pending",
          created_at: "2026-03-18T12:00:00",
          updated_at: "2026-03-18T12:00:00",
          events: [],
          result: null,
          error: null,
          pending_conflict: null,
        }, 202);
      }

      if (url.pathname === "/tasks/task-login-1" && method === "GET") {
        return jsonResponse({
          task_id: "task-login-1",
          task_type: "login",
          state: "succeeded",
          created_at: "2026-03-18T12:00:00",
          updated_at: "2026-03-18T12:00:02",
          events: [
            {
              state: "succeeded",
              timestamp: "2026-03-18T12:00:02",
              message: "登录完成",
              payload: null,
            },
          ],
          result: null,
          error: null,
          pending_conflict: null,
        });
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    }));

    const user = userEvent.setup();
    render(<App />);

    await screen.findByText("账号 B");
    await user.click(screen.getByRole("button", { name: "配置购买状态 账号 B" }));

    const drawer = await screen.findByRole("complementary", { name: "登录配置" });
    expect(within(drawer).getByRole("button", { name: "发起登录" })).not.toBeDisabled();

    await user.click(within(drawer).getByRole("button", { name: "发起登录" }));

    await waitFor(() => {
      expect(calls).toEqual(expect.arrayContaining([
        expect.objectContaining({ method: "POST", pathname: "/accounts/a-2/login" }),
      ]));
    });
    expect(calls).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ pathname: "/diagnostics/browser-environment" }),
      expect.objectContaining({ pathname: "/diagnostics/browser-environment/bootstrap" }),
    ]));
  });
});
