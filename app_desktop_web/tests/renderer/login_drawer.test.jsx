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
  it("starts login, streams task progress, updates status strip and refreshes account rows", async () => {
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

    expect(await within(drawer).findByText("登录完成")).toBeInTheDocument();
    expect(await screen.findByText("登录任务已完成：账号 B")).toBeInTheDocument();
    expect(await screen.findByText("steam-auto")).toBeInTheDocument();
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

    expect(await within(drawer).findByText("登录完成")).toBeInTheDocument();

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
});
