// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


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

    if (url.pathname === "/stats/account-capability" && method === "GET") {
      const rangeMode = url.searchParams.get("range_mode") || "total";
      if (rangeMode === "day") {
        return jsonResponse({
          range_mode: "day",
          date: url.searchParams.get("date"),
          items: [
            {
              account_id: "a1",
              account_display_name: "购买账号-A",
              new_api: { display_text: "182ms · 12次" },
              fast_api: { display_text: "--" },
              browser: { display_text: "340ms · 4次" },
              create_order: { display_text: "520ms · 3次" },
              submit_order: { display_text: "810ms · 3次" },
            },
          ],
        });
      }

      return jsonResponse({
        range_mode: "total",
        items: [
          {
            account_id: "a1",
            account_display_name: "购买账号-A",
            new_api: { display_text: "182ms · 34次" },
            fast_api: { display_text: "91ms · 18次" },
            browser: { display_text: "340ms · 4次" },
            create_order: { display_text: "520ms · 7次" },
            submit_order: { display_text: "810ms · 7次" },
          },
        ],
      });
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}${url.search}`);
  });

  return { calls, fetchImpl };
}


describe("account capability stats page", () => {
  it("switches to the account capability page and renders account performance cells", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "账号能力统计" }));

    const table = await screen.findByRole("table", { name: "账号能力统计表" });
    expect(within(table).getByText("购买账号-A")).toBeInTheDocument();
    expect(within(table).getByText("182ms · 34次")).toBeInTheDocument();
    expect(within(table).getByText("91ms · 18次")).toBeInTheDocument();
    expect(within(table).getByText("340ms · 4次")).toBeInTheDocument();
    expect(within(table).getByText("520ms · 7次")).toBeInTheDocument();
    expect(within(table).getByText("810ms · 7次")).toBeInTheDocument();

    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          method: "GET",
          pathname: "/stats/account-capability",
          search: "?range_mode=total",
        }),
      ]),
    );

    const statsTable = screen.getByRole("table", { name: "账号能力统计表" });
    expect(statsTable.closest(".stats-page")).toHaveClass("stats-page--compact");
  });

  it("supports compact day range filtering controls", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "账号能力统计" }));

    await user.click(await screen.findByRole("button", { name: "按天" }));
    await user.click(screen.getByRole("button", { name: "打开统计日期选择" }));
    const dayDialog = await screen.findByRole("dialog", { name: "选择统计日期" });
    expect(within(dayDialog).getByText("2026年3月")).toBeInTheDocument();
    expect(within(dayDialog).getByText("2026年4月")).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "今天" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "近7天" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "本月" })).toBeInTheDocument();
    expect(within(dayDialog).getByRole("button", { name: "选择日期 2026-04-01" })).toBeDisabled();
    await user.click(within(dayDialog).getByRole("button", { name: "选择日期 2026-03-22" }));
    await user.click(screen.getByRole("button", { name: "刷新统计" }));

    await waitFor(() => {
      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            method: "GET",
            pathname: "/stats/account-capability",
            search: "?range_mode=day&date=2026-03-22",
          }),
        ]),
      );
    });

    const table = screen.getByRole("table", { name: "账号能力统计表" });
    expect(within(table).getByText("182ms · 12次")).toBeInTheDocument();
    expect(within(table).getByText("--")).toBeInTheDocument();
    expect(within(table).getByText("520ms · 3次")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开统计日期选择" })).toHaveTextContent("2026-03-22 00:00:00");
  });
});
