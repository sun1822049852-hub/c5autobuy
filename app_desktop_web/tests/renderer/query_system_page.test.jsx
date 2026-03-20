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


function buildIdleRuntimeStatus() {
  return {
    running: false,
    config_id: null,
    config_name: null,
    message: "未运行",
    account_count: 0,
    started_at: null,
    stopped_at: null,
    total_query_count: 0,
    total_found_count: 0,
    modes: {},
    group_rows: [],
    recent_events: [],
    item_rows: [],
  };
}


function createFetchHarness({ initialRuntimeStatus } = {}) {
  const configs = [
    {
      config_id: "cfg-1",
      name: "白天配置",
      description: "白天轮询",
      enabled: true,
      created_at: "2026-03-19T10:00:00",
      updated_at: "2026-03-19T10:00:00",
      items: [],
      mode_settings: [],
    },
    {
      config_id: "cfg-2",
      name: "夜刀配置",
      description: "夜间专用",
      enabled: true,
      created_at: "2026-03-19T11:00:00",
      updated_at: "2026-03-19T11:00:00",
      items: [],
      mode_settings: [],
    },
  ];

  const details = Object.fromEntries(configs.map((config) => [config.config_id, config]));
  let runtimeStatus = initialRuntimeStatus || buildIdleRuntimeStatus();
  const calls = [];
  let createdCount = 3;

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
      return jsonResponse([]);
    }
    if (url.pathname === "/query-configs" && method === "GET") {
      return jsonResponse(configs);
    }
    if (url.pathname === "/query-configs" && method === "POST") {
      const created = {
        config_id: `cfg-${createdCount}`,
        name: body.name,
        description: body.description,
        enabled: true,
        created_at: "2026-03-19T12:00:00",
        updated_at: "2026-03-19T12:00:00",
        items: [],
        mode_settings: [],
      };
      createdCount += 1;
      configs.push(created);
      details[created.config_id] = created;
      return jsonResponse(created, 201);
    }
    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse({
        modes: {
          new_api: { mode_type: "new_api", available_account_count: 2 },
          fast_api: { mode_type: "fast_api", available_account_count: 1 },
          token: { mode_type: "token", available_account_count: 3 },
        },
      });
    }
    if (url.pathname === "/query-runtime/status" && method === "GET") {
      return jsonResponse(runtimeStatus);
    }
    if (url.pathname === "/query-runtime/start" && method === "POST") {
      const nextConfig = details[body.config_id];
      runtimeStatus = {
        ...buildIdleRuntimeStatus(),
        running: true,
        config_id: body.config_id,
        config_name: nextConfig.name,
        message: "运行中",
      };
      return jsonResponse(runtimeStatus);
    }
    if (url.pathname === "/query-runtime/stop" && method === "POST") {
      runtimeStatus = buildIdleRuntimeStatus();
      return jsonResponse(runtimeStatus);
    }

    const match = url.pathname.match(/^\/query-configs\/([^/]+)$/);
    if (match && method === "GET") {
      return jsonResponse(details[match[1]]);
    }
    if (match && method === "DELETE") {
      const configId = match[1];
      const configIndex = configs.findIndex((config) => config.config_id === configId);
      if (configIndex >= 0) {
        configs.splice(configIndex, 1);
      }
      delete details[configId];
      if (runtimeStatus.config_id === configId) {
        runtimeStatus = buildIdleRuntimeStatus();
      }
      return jsonResponse({}, 204);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
  };
}


describe("query system page", () => {
  it("switches from account center into the real query system page and renders the skeleton", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "查询系统" }));

    expect(await screen.findByRole("heading", { name: "查询工作台" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "查询配置导航" });
    expect(nav).toBeInTheDocument();
    const currentConfigSection = screen.getByText("当前配置").closest("section");
    expect(screen.getByRole("button", { name: "新建配置" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "启动当前配置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
    expect(within(nav).getByText("白天配置")).toBeInTheDocument();
    expect(within(nav).getByText("夜刀配置")).toBeInTheDocument();
    expect(screen.getByText("当前配置")).toBeInTheDocument();
    expect(currentConfigSection).not.toBeNull();
    expect(within(currentConfigSection).getByText("已停止")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存当前配置" })).toBeInTheDocument();
    expect(screen.getByText("new_api 2")).toBeInTheDocument();
    expect(screen.getByText("token 3")).toBeInTheDocument();
  });

  it("creates and deletes configs through centered dialogs", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询系统" }));
    await screen.findByRole("heading", { name: "查询工作台" });

    await user.click(screen.getByRole("button", { name: "新建配置" }));

    const createDialog = await screen.findByRole("dialog", { name: "新建配置" });
    await user.type(within(createDialog).getByLabelText("配置名称"), "新建夜巡配置");
    await user.type(within(createDialog).getByLabelText("配置说明"), "给夜间用");
    await user.click(within(createDialog).getByRole("button", { name: "保存配置" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "新建夜巡配置" })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: "查询配置导航" });
    expect(within(nav).getByText("新建夜巡配置")).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: "删除配置 夜刀配置" }));
    const deleteDialog = await screen.findByRole("dialog", { name: "删除配置" });
    expect(within(deleteDialog).getByText("夜刀配置")).toBeInTheDocument();
    await user.click(within(deleteDialog).getByRole("button", { name: "确认删除" }));

    await waitFor(() => {
      expect(within(nav).queryByText("夜刀配置")).not.toBeInTheDocument();
    });

    expect(harness.calls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          body: { description: "给夜间用", name: "新建夜巡配置" },
          method: "POST",
          pathname: "/query-configs",
        }),
        expect.objectContaining({
          body: null,
          method: "DELETE",
          pathname: "/query-configs/cfg-2",
        }),
      ]),
    );
  });

  it("loads the selected config detail when switching config items in the left nav", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询系统" }));
    await screen.findByRole("heading", { name: "查询工作台" });

    const nav = screen.getByRole("navigation", { name: "查询配置导航" });
    await user.click(within(nav).getByRole("button", { name: /^夜刀配置/ }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    });
    expect(screen.getByText("夜间专用")).toBeInTheDocument();
  });

  it("shows waiting status when backend reports a config is waiting for accounts", async () => {
    const harness = createFetchHarness({
      initialRuntimeStatus: {
        ...buildIdleRuntimeStatus(),
        config_id: "cfg-2",
        config_name: "夜刀配置",
        message: "等待购买账号恢复",
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询系统" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: "查询配置导航" });
    expect(within(nav).getByRole("button", { name: /^夜刀配置/ })).toHaveTextContent("等待账号");
    const currentConfigSection = screen.getByText("当前配置").closest("section");
    expect(currentConfigSection).not.toBeNull();
    expect(within(currentConfigSection).getByText("等待账号")).toBeInTheDocument();
    expect(screen.getByText("等待购买账号恢复")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
  });

  it("shows backend runtime ownership but keeps query page as config-only management", async () => {
    const harness = createFetchHarness({
      initialRuntimeStatus: {
        ...buildIdleRuntimeStatus(),
        running: true,
        config_id: "cfg-1",
        config_name: "白天配置",
        message: "运行中",
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "查询系统" }));
    await screen.findByRole("heading", { name: "白天配置" });

    const nav = screen.getByRole("navigation", { name: "查询配置导航" });
    expect(within(nav).getByRole("button", { name: /^白天配置/ })).toHaveTextContent("运行中");
    expect(within(nav).getByRole("button", { name: /^夜刀配置/ })).toHaveTextContent("已停止");
    expect(screen.queryByRole("button", { name: "启动当前配置" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "停止当前配置" })).not.toBeInTheDocument();
  });
});
