// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
          status_code: 401,
          request_method: "GET",
          request_path: "/openapi/query",
          response_text: "not login",
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
          status_code: 409,
          request_method: "POST",
          request_path: "/purchase/orders",
          response_text: "{\"error\":\"sold out\"}",
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
          error: "浏览器关闭",
          pending_conflict: null,
          events: [
            { state: "pending", timestamp: "2026-03-25T19:58:00", message: "创建任务" },
            {
              state: "failed",
              timestamp: "2026-03-25T19:58:30",
              message: "浏览器关闭",
              payload: {
                status_code: 500,
                request_method: "POST",
                request_path: "/accounts/a-3/login",
                response_text: "browser crashed",
              },
            },
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


function createFetchHarness({ snapshots } = {}) {
  const diagnosticsSnapshots = (snapshots?.length ? snapshots : [buildDiagnosticsSnapshot()]).map((snapshot) => ({
    ...snapshot,
    query: {
      ...snapshot.query,
      recent_events: [...(snapshot.query?.recent_events || [])],
      account_rows: [...(snapshot.query?.account_rows || [])],
      mode_rows: [...(snapshot.query?.mode_rows || [])],
    },
    purchase: {
      ...snapshot.purchase,
      recent_events: [...(snapshot.purchase?.recent_events || [])],
      account_rows: [...(snapshot.purchase?.account_rows || [])],
    },
    login_tasks: {
      ...snapshot.login_tasks,
      recent_tasks: [...(snapshot.login_tasks?.recent_tasks || [])],
    },
  }));
  let diagnosticsCallCount = 0;
  return vi.fn(async (input) => {
    const url = new URL(input);

    if (url.pathname === "/account-center/accounts") {
      return {
        ok: true,
        json: async () => [],
      };
    }

    if (url.pathname === "/diagnostics/sidebar") {
      const snapshot = diagnosticsSnapshots[Math.min(diagnosticsCallCount, diagnosticsSnapshots.length - 1)];
      diagnosticsCallCount += 1;
      return {
        ok: true,
        json: async () => snapshot,
      };
    }

    throw new Error(`Unhandled request: ${url.pathname}`);
  });
}


describe("diagnostics page", () => {
  it("does not poll diagnostics until the diagnostics page is opened", async () => {
    const fetchImpl = createFetchHarness();
    installDesktopApp(fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole("button", { name: "账号中心" });

    expect(
      fetchImpl.mock.calls.some(([input]) => new URL(input).pathname === "/diagnostics/sidebar"),
    ).toBe(false);

    await user.click(screen.getByRole("button", { name: "通用诊断" }));

    await screen.findByRole("complementary", { name: "通用诊断面板" });
    expect(
      fetchImpl.mock.calls.some(([input]) => new URL(input).pathname === "/diagnostics/sidebar"),
    ).toBe(true);
  });

  it("moves diagnostics into a dedicated page instead of rendering a persistent shell sidebar", async () => {
    installDesktopApp(createFetchHarness());
    const user = userEvent.setup();

    render(<App />);

    expect(await screen.findByRole("button", { name: "通用诊断" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "通用诊断面板" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "账号中心" })).toHaveClass("is-active");

    await user.click(screen.getByRole("button", { name: "通用诊断" }));

    const panel = await screen.findByRole("complementary", { name: "通用诊断面板" });
    expect(panel).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "通用诊断" })).toHaveClass("is-active");
    expect(within(panel).getAllByText("查询配置A")).toHaveLength(2);
    expect(within(panel).getByRole("tab", { name: "查询" })).toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "购买" })).toBeInTheDocument();
    expect(within(panel).getByRole("tab", { name: "登录任务" })).toBeInTheDocument();
    expect(within(panel).getByText("42")).toBeInTheDocument();
    expect(within(panel).getByText("8")).toBeInTheDocument();
    expect(within(panel).getByText("异常查询账号-1")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: /查询事件日志/i })).toBeInTheDocument();
    expect(within(panel).getByText("1")).toBeInTheDocument();
    expect(within(panel).getAllByText("token invalid").length).toBeGreaterThan(0);
  });

  it("keeps showing captured summary and account errors even after later snapshots clear them", async () => {
    const initialSnapshot = buildDiagnosticsSnapshot();
    const laterSnapshot = buildDiagnosticsSnapshot();
    laterSnapshot.summary.last_error = "";
    laterSnapshot.query.last_error = "";
    laterSnapshot.query.account_rows = [];
    laterSnapshot.query.recent_events = [];
    installDesktopApp(createFetchHarness({
      snapshots: [initialSnapshot, laterSnapshot],
    }));

    render(<App />);

    expect(screen.getByRole("button", { name: "账号中心" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "通用诊断" }));
    const panel = await screen.findByRole("complementary", { name: "通用诊断面板" });

    await waitFor(() => {
      expect(within(panel).getByText("异常查询账号-1")).toBeInTheDocument();
    });

    await act(async () => {
      await new Promise((resolve) => {
        window.setTimeout(resolve, 1600);
      });
    });

    expect(within(panel).getByText("异常查询账号-1")).toBeInTheDocument();
    expect(within(panel).getAllByText("token invalid").length).toBeGreaterThan(0);
    expect(within(panel).getByRole("button", { name: /查询事件日志/i })).toBeInTheDocument();
    expect(within(panel).getByText("0")).toBeInTheDocument();
  });

  it("refreshes the query events modal with the latest snapshot instead of retaining stale rows", async () => {
    const initialSnapshot = buildDiagnosticsSnapshot();
    const laterSnapshot = buildDiagnosticsSnapshot();
    laterSnapshot.query.updated_at = "2026-03-25T20:21:00";
    laterSnapshot.updated_at = "2026-03-25T20:21:00";
    laterSnapshot.query.recent_events = [
      {
        timestamp: "2026-03-25T20:21:00",
        level: "info",
        mode_type: "new_api",
        account_id: "query-good-2",
        account_display_name: "查询账号-2",
        query_item_id: "item-2",
        query_item_name: "M4A1-S | Blue Phosphor",
        message: "查询事件-2",
        match_count: 2,
        total_price: 456.78,
        total_wear_sum: 0.09,
        latency_ms: 66,
        error: null,
        status_code: 200,
        request_method: "GET",
        request_path: "/openapi/query",
        response_text: "{\"ok\":true}",
      },
    ];
    installDesktopApp(createFetchHarness({
      snapshots: [initialSnapshot, laterSnapshot],
    }));
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "通用诊断" }));

    const panel = await screen.findByRole("complementary", { name: "通用诊断面板" });
    await user.click(within(panel).getByRole("button", { name: /查询事件日志/i }));

    const dialog = await screen.findByRole("dialog", { name: "查询事件日志" });
    expect(within(dialog).getByText("查询事件-1")).toBeInTheDocument();
    expect(within(dialog).getByText("2026-03-25T20:00:01")).toBeInTheDocument();

    await act(async () => {
      await new Promise((resolve) => {
        window.setTimeout(resolve, 1600);
      });
    });

    await waitFor(() => {
      expect(within(dialog).getByText("查询事件-2")).toBeInTheDocument();
    });
    expect(within(dialog).getByText("2026-03-25T20:21:00")).toBeInTheDocument();
    expect(within(dialog).queryByText("查询事件-1")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("2026-03-25T20:00:01")).not.toBeInTheDocument();
    expect(within(dialog).getByText("查询事件日志")).toBeInTheDocument();
  });
});
