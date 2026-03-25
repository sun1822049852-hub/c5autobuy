// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


function buildDiagnosticsSnapshot() {
  return {
    summary: {
      backend_online: true,
      query_running: true,
      purchase_running: true,
      active_query_config_name: "查询配置A",
      last_error: "token invalid",
      updated_at: "2026-03-25T20:00:00",
    },
    query: {
      running: true,
      config_id: "cfg-1",
      config_name: "查询配置A",
      message: "运行中",
      total_query_count: 42,
      total_found_count: 8,
      last_error: "token invalid",
      updated_at: "2026-03-25T20:00:00",
      mode_rows: [
        {
          mode_type: "new_api",
          enabled: true,
          eligible_account_count: 1,
          active_account_count: 1,
          query_count: 12,
          found_count: 3,
          last_error: null,
        },
        {
          mode_type: "token",
          enabled: true,
          eligible_account_count: 2,
          active_account_count: 0,
          query_count: 30,
          found_count: 5,
          last_error: "token invalid",
        },
      ],
      account_rows: [
        {
          account_id: "query-bad-1",
          display_name: "异常查询账号-1",
          mode_type: "token",
          active: false,
          query_count: 10,
          found_count: 0,
          last_error: "token invalid",
          disabled_reason: null,
          last_seen_at: "2026-03-25T19:59:00",
        },
      ],
      recent_events: [
        {
          timestamp: "2026-03-25T20:00:01",
          level: "error",
          mode_type: "token",
          account_id: "query-bad-1",
          account_display_name: "异常查询账号-1",
          query_item_id: "item-1",
          query_item_name: "AK-47 | Redline",
          message: "查询事件-1",
          match_count: 1,
          total_price: 123.45,
          total_wear_sum: 0.1,
          latency_ms: 88,
          error: "token invalid",
        },
      ],
    },
    purchase: {
      running: true,
      message: "运行中",
      active_account_count: 2,
      total_purchased_count: 9,
      last_error: "库存刷新失败",
      updated_at: "2026-03-25T20:00:01",
      account_rows: [
        {
          account_id: "purchase-bad-1",
          display_name: "异常购买账号-1",
          purchase_capability_state: "bound",
          purchase_pool_state: "paused_no_inventory",
          purchase_disabled: false,
          selected_inventory_name: "主仓",
          selected_inventory_remaining_capacity: 0,
          last_error: "库存刷新失败",
        },
      ],
      recent_events: [
        {
          occurred_at: "2026-03-25T20:00:02",
          status: "failed",
          message: "购买事件-1",
          query_item_name: "AK-47 | Redline",
          source_mode_type: "token",
          total_price: 123.45,
          total_wear_sum: 0.1,
        },
      ],
    },
    login_tasks: {
      running_count: 1,
      conflict_count: 1,
      failed_count: 1,
      updated_at: "2026-03-25T20:00:03",
      recent_tasks: [
        {
          task_id: "task-1",
          account_id: "a-1",
          account_display_name: "账号 A",
          state: "waiting_for_scan",
          started_at: "2026-03-25T20:00:00",
          updated_at: "2026-03-25T20:00:01",
          last_message: "等待扫码",
          pending_conflict: null,
          events: [
            { state: "pending", timestamp: "2026-03-25T20:00:00", message: "创建任务" },
            { state: "waiting_for_scan", timestamp: "2026-03-25T20:00:01", message: "等待扫码" },
          ],
        },
        {
          task_id: "task-2",
          account_id: "a-2",
          account_display_name: "账号 B",
          state: "conflict",
          started_at: "2026-03-25T19:59:00",
          updated_at: "2026-03-25T20:00:00",
          last_message: "账号冲突",
          pending_conflict: { existing_account_id: "a-2" },
          events: [
            { state: "pending", timestamp: "2026-03-25T19:59:00", message: "创建任务" },
            { state: "conflict", timestamp: "2026-03-25T20:00:00", message: "账号冲突" },
          ],
        },
        {
          task_id: "task-3",
          account_id: "a-3",
          account_display_name: "账号 C",
          state: "failed",
          started_at: "2026-03-25T19:58:00",
          updated_at: "2026-03-25T19:58:30",
          last_message: "浏览器关闭",
          pending_conflict: null,
          events: [
            { state: "pending", timestamp: "2026-03-25T19:58:00", message: "创建任务" },
            { state: "failed", timestamp: "2026-03-25T19:58:30", message: "浏览器关闭" },
          ],
        },
      ],
    },
    updated_at: "2026-03-25T20:00:03",
  };
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
  const diagnosticsSnapshot = buildDiagnosticsSnapshot();
  return vi.fn(async (input) => {
    const url = new URL(input);

    if (url.pathname === "/account-center/accounts") {
      return {
        ok: true,
        json: async () => [],
      };
    }

    if (url.pathname === "/diagnostics/sidebar") {
      return {
        ok: true,
        json: async () => diagnosticsSnapshot,
      };
    }

    throw new Error(`Unhandled request: ${url.pathname}`);
  });
}


describe("diagnostics sidebar", () => {
  it("renders the diagnostics panel in the shell and shows query diagnostics by default", async () => {
    installDesktopApp(createFetchHarness());

    render(<App />);

    const panel = await screen.findByRole("complementary", { name: "通用诊断面板" });
    expect(panel).toBeInTheDocument();
    expect(within(panel).getAllByText("查询配置A")).toHaveLength(2);
    expect(within(panel).getByRole("tab", { name: "查询" })).toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "购买" })).toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "登录任务" })).toBeInTheDocument();
    expect(within(panel).getByText("42")).toBeInTheDocument();
    expect(within(panel).getByText("8")).toBeInTheDocument();
    expect(within(panel).getByText("异常查询账号-1")).toBeInTheDocument();
    expect(within(panel).getByText("查询事件-1")).toBeInTheDocument();
    expect(within(panel).getAllByText("token invalid").length).toBeGreaterThan(0);
  });

  it("switches between purchase and login diagnostics tabs without leaving the current page", async () => {
    installDesktopApp(createFetchHarness());
    const user = userEvent.setup();

    render(<App />);

    const panel = await screen.findByRole("complementary", { name: "通用诊断面板" });
    await user.click(within(panel).getByRole("tab", { name: "购买" }));

    await waitFor(() => {
      expect(within(panel).getByText("异常购买账号-1")).toBeInTheDocument();
    });
    expect(within(panel).getByText("购买事件-1")).toBeInTheDocument();

    await user.click(within(panel).getByRole("tab", { name: "登录任务" }));

    await waitFor(() => {
      expect(within(panel).getAllByText("等待扫码").length).toBeGreaterThan(0);
    });
    expect(within(panel).getAllByText("账号冲突").length).toBeGreaterThan(0);
    expect(within(panel).getAllByText("浏览器关闭").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "账号中心" })).toHaveClass("is-active");
  });
});
