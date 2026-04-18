// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


function createTodayDateString() {
  return new Date().toISOString().slice(0, 10);
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
  const calls = [];
  const fetchImpl = vi.fn(async (input, options = {}) => {
    const url = new URL(input);
    const method = String(options.method ?? "GET").toUpperCase();
    calls.push({
      method,
      pathname: url.pathname,
      search: url.search,
    });

    if (url.pathname === "/account-center/accounts" && method === "GET") {
      return jsonResponse([]);
    }

    if (url.pathname === "/stats/query-items" && method === "GET") {
      const rangeMode = url.searchParams.get("range_mode") || "total";
      if (rangeMode === "day") {
        return jsonResponse({
          range_mode: "day",
          date: url.searchParams.get("date"),
          items: [
            {
              external_item_id: "ext-1",
              item_name: "AK-47 | Redline",
              product_url: "https://example.com/items/ext-1",
              query_execution_count: 4,
              matched_product_count: 2,
              purchase_success_count: 1,
              purchase_failed_count: 1,
              source_mode_stats: [
                { mode_type: "new_api", hit_count: 2, account_display_name: "查询账号A" },
              ],
              updated_at: "2026-03-22T10:00:00",
            },
          ],
        });
      }
      if (rangeMode === "range") {
        return jsonResponse({
          range_mode: "range",
          start_date: url.searchParams.get("start_date"),
          end_date: url.searchParams.get("end_date"),
          items: [
            {
              external_item_id: "ext-1",
              item_name: "AK-47 | Redline",
              product_url: "https://example.com/items/ext-1",
              query_execution_count: 8,
              matched_product_count: 3,
              purchase_success_count: 2,
              purchase_failed_count: 1,
              source_mode_stats: [
                { mode_type: "fast_api", hit_count: 3, account_display_name: "查询账号B" },
              ],
              updated_at: "2026-03-22T10:00:00",
            },
          ],
        });
      }

      return jsonResponse({
        range_mode: "total",
        items: [
          {
            external_item_id: "ext-1",
            item_name: "AK-47 | Redline",
            product_url: "https://example.com/items/ext-1",
            query_execution_count: 12,
            matched_product_count: 5,
            purchase_success_count: 2,
            purchase_failed_count: 3,
            source_mode_stats: [
              { mode_type: "new_api", hit_count: 3, account_display_name: "查询账号A" },
              { mode_type: "fast_api", hit_count: 2, account_display_name: "查询账号B" },
            ],
            updated_at: "2026-03-22T10:00:00",
          },
        ],
      });
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}${url.search}`);
  });

  return { calls, fetchImpl };
}


describe("query stats page", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-03-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("switches to the query stats page and defaults to today's item stats", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();
    const today = createTodayDateString();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询统计" }));

    const table = await screen.findByRole("table", { name: "查询统计表" });
    expect(within(table).getByText("下单失败件数")).toBeInTheDocument();
    expect(within(table).getByText("AK-47 | Redline")).toBeInTheDocument();
    expect(within(table).getByText("4")).toBeInTheDocument();
    expect(within(table).getByText("2")).toBeInTheDocument();
    expect(within(table).getAllByText("1")).toHaveLength(2);
    expect(within(table).getByText("查询账号A / api查询器 2")).toBeInTheDocument();

    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: "GET",
          pathname: "/stats/query-items",
          search: `?range_mode=day&date=${today}`,
        }),
      ]),
    );

    expect(screen.getByRole("button", { name: "打开统计时间选择" })).toHaveTextContent(`${today} 00:00:00`);
    expect(table.closest(".stats-page")).toHaveClass("stats-page--compact");
  });

  it("supports compact day and range filtering controls", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询统计" }));

    expect(screen.queryByRole("button", { name: "按天" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "时间段" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开统计时间选择" }));
    const dayDialog = await screen.findByRole("dialog", { name: "选择统计日期" });
    expect(within(dayDialog).getByText("2026年3月")).toBeInTheDocument();
    expect(within(dayDialog).getByText("2026年4月")).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "总计" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "今天" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "近7天" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "本月" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "选择日期 2026-03-28" })).toBeDisabled();
    await user.click(within(dayDialog).getByRole("button", { name: "选择日期 2026-03-21" }));
    await user.click(screen.getByRole("button", { name: "刷新统计" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "GET",
            pathname: "/stats/query-items",
            search: "?range_mode=day&date=2026-03-21",
          }),
        ]),
      );
    });

    const table = screen.getByRole("table", { name: "查询统计表" });
    expect(within(table).getByText("4")).toBeInTheDocument();
    expect(within(table).getByText("2")).toBeInTheDocument();
    expect(within(table).getAllByText("1")).toHaveLength(2);
    expect(within(table).getByText("查询账号A / api查询器 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开统计时间选择" })).toHaveTextContent("2026-03-21 00:00:00");

    await user.click(screen.getByRole("button", { name: "打开统计时间选择" }));
    const reopenedDayDialog = await screen.findByRole("dialog", { name: "选择统计日期" });
    await user.click(within(reopenedDayDialog).getByRole("button", { name: "近7天" }));
    const rangeDialog = await screen.findByRole("dialog", { name: "选择统计时间段" });
    expect(within(rangeDialog).getByText("2026年3月")).toBeInTheDocument();
    expect(within(rangeDialog).getByText("2026年4月")).toBeInTheDocument();
    expect(within(rangeDialog).getByRole("button", { name: "总计" })).toBeInTheDocument();
    expect(within(rangeDialog).getByRole("button", { name: "今天" })).toBeInTheDocument();
    expect(within(rangeDialog).getByRole("button", { name: "近7天" })).toBeInTheDocument();
    expect(within(rangeDialog).getByRole("button", { name: "本月" })).toBeInTheDocument();
    expect(within(rangeDialog).getByRole("button", { name: "选择日期 2026-03-28" })).toBeDisabled();
    await user.click(within(rangeDialog).getByRole("button", { name: /^开始日期 / }));
    await user.click(within(rangeDialog).getByRole("button", { name: "选择日期 2026-03-21" }));
    await user.click(screen.getByRole("button", { name: "刷新统计" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "GET",
            pathname: "/stats/query-items",
            search: "?range_mode=range&start_date=2026-03-21&end_date=2026-03-25",
          }),
        ]),
      );
    });

    expect(screen.getByRole("button", { name: "打开统计时间选择" })).toHaveTextContent(
      "2026-03-21 00:00:00 ~ 2026-03-25 23:59:59",
    );
    expect(within(table).getByText("8")).toBeInTheDocument();
    expect(within(table).getByText("查询账号B / api高速查询器 3")).toBeInTheDocument();
  });

  it("closes the stats picker when clicking outside the picker", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询统计" }));

    await user.click(screen.getByRole("button", { name: "打开统计时间选择" }));
    expect(await screen.findByRole("dialog", { name: "选择统计日期" })).toBeInTheDocument();

    await user.click(screen.getByText("按商品聚合命中、成功、下单失败件数与来源统计。"));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "选择统计日期" })).not.toBeInTheDocument();
    });
  });

  it("shows raw http details when query stats loading fails with an unhandled backend string", async () => {
    const today = createTodayDateString();
    installDesktopApp(vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();

      if (url.pathname === "/account-center/accounts" && method === "GET") {
        return jsonResponse([]);
      }

      if (url.pathname === "/stats/query-items" && method === "GET") {
        return {
          ok: false,
          status: 401,
          text: async () => "not login",
        };
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}${url.search}`);
    }));

    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询统计" }));

    const errorPanel = await screen.findByRole("alert");
    expect(within(errorPanel).getByText("not login")).toBeInTheDocument();
    expect(within(errorPanel).getByText("HTTP 401")).toBeInTheDocument();
    expect(within(errorPanel).getByText(`GET /stats/query-items?range_mode=day&date=${today}`)).toBeInTheDocument();
    expect(within(errorPanel).getByText("原始返回：not login")).toBeInTheDocument();
  });
});
