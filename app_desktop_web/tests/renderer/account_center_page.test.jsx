// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
      api_key: "api-a",
      proxy_display: "直连",
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
      api_key: null,
      proxy_display: "http://127.0.0.1:9000",
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
      api_key: "api-c",
      proxy_display: "socks5://127.0.0.1:9900",
      purchase_status_code: "inventory_full",
      purchase_status_text: "库存已满",
    },
  ];
}


describe("account center page", () => {
  it("renders shell navigation, overview cards, account table and status strip", async () => {
    installDesktopApp(
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => accountRows(),
      }),
    );

    render(<App />);

    expect(screen.getByRole("button", { name: "账号中心" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查询系统" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "购买系统" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    expect(screen.getByText("总账号")).toBeInTheDocument();
    expect(screen.getByText("未登录")).toBeInTheDocument();
    expect(screen.getByText("无 API Key")).toBeInTheDocument();
    expect(screen.getByText("可购买")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "C5昵称" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "API Key" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "购买状态" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "代理" })).toBeInTheDocument();

    expect(screen.getByText("最近登录任务")).toBeInTheDocument();
    expect(screen.getByText("最近错误")).toBeInTheDocument();
    expect(screen.getByText("最近修改")).toBeInTheDocument();

    expect(screen.getByText("账号 A")).toBeInTheDocument();
    expect(screen.getByText("账号 B")).toBeInTheDocument();
    expect(screen.getByText("账号 C")).toBeInTheDocument();
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
});
