// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../src/App.jsx";


const ALL_MODES = ["new_api", "fast_api", "token"];


function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}


function buildModeAllocations(values = {}) {
  return ALL_MODES.map((modeType) => ({
    mode_type: modeType,
    target_dedicated_count: values[modeType] ?? 0,
  }));
}


function delayedJsonResponse(payload, status = 200, delayMs = 0) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      });
    }, delayMs);
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


function buildConfigDetail() {
  return {
    config_id: "cfg-1",
    name: "白天配置",
    description: "白天轮询",
    enabled: true,
    created_at: "2026-03-19T10:00:00",
    updated_at: "2026-03-19T10:00:00",
    mode_settings: [],
    items: [
      {
        query_item_id: "item-1",
        config_id: "cfg-1",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267001",
        external_item_id: "1380979899390267001",
        item_name: "AK-47 | Redline",
        market_hash_name: "AK-47 | Redline (Field-Tested)",
        min_wear: 0.1,
        max_wear: 0.7,
        detail_min_wear: 0.1,
        detail_max_wear: 0.25,
        max_price: 199,
        last_market_price: 188.88,
        last_detail_sync_at: "2026-03-19T10:05:00",
        manual_paused: false,
        mode_allocations: buildModeAllocations({ new_api: 1 }),
        sort_order: 0,
        created_at: "2026-03-19T10:00:00",
        updated_at: "2026-03-19T10:00:00",
      },
      {
        query_item_id: "item-2",
        config_id: "cfg-1",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267002",
        external_item_id: "1380979899390267002",
        item_name: "AWP | Asiimov",
        market_hash_name: "AWP | Asiimov (Field-Tested)",
        min_wear: 0.18,
        max_wear: 1.0,
        detail_min_wear: 0.18,
        detail_max_wear: 0.45,
        max_price: 999,
        last_market_price: 955.55,
        last_detail_sync_at: "2026-03-19T10:06:00",
        manual_paused: false,
        mode_allocations: buildModeAllocations({ fast_api: 1 }),
        sort_order: 1,
        created_at: "2026-03-19T10:00:00",
        updated_at: "2026-03-19T10:00:00",
      },
      {
        query_item_id: "item-3",
        config_id: "cfg-1",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267003",
        external_item_id: "1380979899390267003",
        item_name: "M4A1-S | Blue Phosphor",
        market_hash_name: "M4A1-S | Blue Phosphor (Factory New)",
        min_wear: 0.0,
        max_wear: 0.08,
        detail_min_wear: 0.0,
        detail_max_wear: 0.03,
        max_price: 2888,
        last_market_price: 2555.55,
        last_detail_sync_at: "2026-03-19T10:07:00",
        manual_paused: true,
        mode_allocations: buildModeAllocations({ new_api: 1, token: 1 }),
        sort_order: 2,
        created_at: "2026-03-19T10:00:00",
        updated_at: "2026-03-19T10:00:00",
      },
    ],
  };
}


function buildRuntimeStatus() {
  return {
    running: true,
    config_id: "cfg-1",
    config_name: "白天配置",
    message: "白天配置运行中",
    account_count: 3,
    started_at: "2026-03-19T11:00:00",
    stopped_at: null,
    total_query_count: 0,
    total_found_count: 0,
    modes: {},
    group_rows: [],
    recent_events: [],
    item_rows: [
      {
        query_item_id: "item-1",
        item_name: "AK-47 | Redline",
        max_price: 199,
        min_wear: 0.1,
        max_wear: 0.7,
        detail_min_wear: 0.1,
        detail_max_wear: 0.25,
        manual_paused: false,
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 1,
            actual_dedicated_count: 1,
            status: "dedicated",
            status_message: "专属中 1/1",
          },
          fast_api: {
            mode_type: "fast_api",
            target_dedicated_count: 0,
            actual_dedicated_count: 0,
            status: "shared",
            status_message: "共享中",
          },
          token: {
            mode_type: "token",
            target_dedicated_count: 0,
            actual_dedicated_count: 0,
            status: "shared",
            status_message: "共享中",
          },
        },
      },
      {
        query_item_id: "item-2",
        item_name: "AWP | Asiimov",
        max_price: 999,
        min_wear: 0.18,
        max_wear: 1.0,
        detail_min_wear: 0.18,
        detail_max_wear: 0.45,
        manual_paused: false,
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 0,
            actual_dedicated_count: 0,
            status: "shared",
            status_message: "共享中",
          },
          fast_api: {
            mode_type: "fast_api",
            target_dedicated_count: 1,
            actual_dedicated_count: 0,
            status: "no_capacity",
            status_message: "无可用账号 0/1",
          },
          token: {
            mode_type: "token",
            target_dedicated_count: 0,
            actual_dedicated_count: 0,
            status: "shared",
            status_message: "共享中",
          },
        },
      },
      {
        query_item_id: "item-3",
        item_name: "M4A1-S | Blue Phosphor",
        max_price: 2888,
        min_wear: 0.0,
        max_wear: 0.08,
        detail_min_wear: 0.0,
        detail_max_wear: 0.03,
        manual_paused: true,
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 1,
            actual_dedicated_count: 1,
            status: "dedicated",
            status_message: "专属中 1/1",
          },
          fast_api: {
            mode_type: "fast_api",
            target_dedicated_count: 0,
            actual_dedicated_count: 0,
            status: "shared",
            status_message: "共享中",
          },
          token: {
            mode_type: "token",
            target_dedicated_count: 1,
            actual_dedicated_count: 0,
            status: "no_capacity",
            status_message: "无可用账号 0/1",
          },
        },
      },
    ],
  };
}


function createFetchHarness({
  capacityModes = {
    new_api: { mode_type: "new_api", available_account_count: 2 },
    fast_api: { mode_type: "fast_api", available_account_count: 1 },
    token: { mode_type: "token", available_account_count: 3 },
  },
  saveDelayMs = 0,
} = {}) {
  let detail = buildConfigDetail();
  const runtimeStatus = buildRuntimeStatus();
  const calls = [];
  let createdCount = 4;

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
      return jsonResponse([
        {
          config_id: detail.config_id,
          name: detail.name,
          description: detail.description,
          enabled: detail.enabled,
          created_at: detail.created_at,
          updated_at: detail.updated_at,
          items: [],
          mode_settings: [],
        },
      ]);
    }
    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse({ modes: capacityModes });
    }
    if (url.pathname === "/query-runtime/status" && method === "GET") {
      return jsonResponse(runtimeStatus);
    }
    if (url.pathname === "/query-configs/cfg-1" && method === "GET") {
      return jsonResponse(detail);
    }
    if (url.pathname === "/query-items/parse-url" && method === "POST") {
      return jsonResponse({
        product_url: body.product_url,
        external_item_id: "1380979899390267000",
      });
    }
    if (url.pathname === "/query-items/fetch-detail" && method === "POST") {
      return jsonResponse({
        product_url: body.product_url,
        external_item_id: body.external_item_id,
        item_name: "M4A1-S | Printstream",
        market_hash_name: "M4A1-S | Printstream (Field-Tested)",
        min_wear: 0.02,
        max_wear: 0.8,
        last_market_price: 555.0,
      });
    }

    const updateMatch = url.pathname.match(/^\/query-configs\/cfg-1\/items\/([^/]+)$/);
    if (updateMatch && method === "PATCH") {
      const queryItemId = updateMatch[1];
      detail = {
        ...detail,
        items: detail.items.map((item) => (
          item.query_item_id === queryItemId
            ? {
              ...item,
              detail_min_wear: body.detail_min_wear,
              detail_max_wear: body.detail_max_wear,
              max_price: body.max_price,
              manual_paused: body.manual_paused,
              mode_allocations: buildModeAllocations(body.mode_allocations || {}),
              updated_at: "2026-03-19T12:00:00",
            }
            : item
        )),
      };
      return delayedJsonResponse(
        detail.items.find((item) => item.query_item_id === queryItemId),
        200,
        saveDelayMs,
      );
    }
    if (updateMatch && method === "DELETE") {
      const queryItemId = updateMatch[1];
      detail = {
        ...detail,
        items: detail.items.filter((item) => item.query_item_id !== queryItemId),
      };
      return delayedJsonResponse({}, 204, saveDelayMs);
    }

    if (url.pathname === "/query-configs/cfg-1/items" && method === "POST") {
      const createdItem = {
        query_item_id: `item-${createdCount}`,
        config_id: "cfg-1",
        product_url: body.product_url,
        external_item_id: "1380979899390267000",
        item_name: "M4A1-S | Printstream",
        market_hash_name: "M4A1-S | Printstream (Field-Tested)",
        min_wear: 0.02,
        max_wear: 0.8,
        detail_min_wear: body.detail_min_wear,
        detail_max_wear: body.detail_max_wear,
        max_price: body.max_price,
        last_market_price: 555.0,
        last_detail_sync_at: "2026-03-19T12:00:00",
        manual_paused: body.manual_paused,
        mode_allocations: buildModeAllocations(body.mode_allocations || {}),
        sort_order: detail.items.length,
        created_at: "2026-03-19T12:00:00",
        updated_at: "2026-03-19T12:00:00",
      };
      createdCount += 1;
      detail = {
        ...detail,
        items: [...detail.items, createdItem],
      };
      return delayedJsonResponse(createdItem, 201, saveDelayMs);
    }

    throw new Error(`Unhandled request: ${method} ${url.pathname}`);
  });

  return {
    calls,
    fetchImpl,
  };
}


async function openQuerySystem(user) {
  render(<App />);
  await user.click(await screen.findByRole("button", { name: "配置管理" }));
  await screen.findByRole("heading", { name: "白天配置" });
}


describe("query system editing", () => {
  it("renders item rows and recalculates remaining dedicated capacity through item dialogs", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    const itemTwo = screen.getByRole("region", { name: "商品 AWP | Asiimov" });

    expect(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" })).toHaveTextContent("199");
    expect(within(itemOne).getByRole("button", { name: "修改磨损 AK-47 | Redline" })).toHaveTextContent("0.1 ~ 0.25");
    expect(within(itemOne).getByRole("button", { name: "修改 new_api AK-47 | Redline" })).toHaveTextContent("专属中 1/1");
    expect(within(itemTwo).getByRole("button", { name: "修改 fast_api AWP | Asiimov" })).toHaveTextContent("无可用账号 0/1");
    const itemThree = screen.getByRole("region", { name: "商品 M4A1-S | Blue Phosphor" });
    expect(within(itemThree).getByRole("button", { name: "修改 new_api M4A1-S | Blue Phosphor" })).toHaveTextContent("手动暂停");
    expect(within(itemThree).getByRole("button", { name: "修改 token M4A1-S | Blue Phosphor" })).toHaveTextContent("手动暂停");

    await user.click(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" }));
    const editorOne = await screen.findByRole("dialog", { name: "编辑商品" });

    expect(within(editorOne).getByText("天然磨损范围 0.1 ~ 0.7")).toBeInTheDocument();
    expect(within(editorOne).getByLabelText("配置最小磨损")).toHaveValue(0.1);
    expect(within(editorOne).getByLabelText("配置最大磨损")).toHaveValue(0.25);
    expect(within(editorOne).getByLabelText("最高价格")).toHaveValue(199);
    expect(within(editorOne).getByLabelText("new_api 专属目标")).toHaveValue(1);
    expect(within(editorOne).getByText("new_api 还可分配 2")).toBeInTheDocument();
    await user.click(within(editorOne).getByRole("button", { name: "取消" }));

    await user.click(within(itemTwo).getByRole("button", { name: "修改价格 AWP | Asiimov" }));
    const editorTwo = await screen.findByRole("dialog", { name: "编辑商品" });
    const itemTwoNewApi = within(editorTwo).getByLabelText("new_api 专属目标");
    await user.clear(itemTwoNewApi);
    await user.type(itemTwoNewApi, "1");
    await user.click(within(editorTwo).getByRole("button", { name: "应用修改" }));

    await user.click(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" }));
    const editorOneAgain = await screen.findByRole("dialog", { name: "编辑商品" });
    expect(within(editorOneAgain).getByText("new_api 还可分配 1")).toBeInTheDocument();
  });

  it("adds a draft item from the centered create dialog and saves both existing and new items", async () => {
    const harness = createFetchHarness({ saveDelayMs: 40 });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    try {
      await openQuerySystem(user);

      const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
      await user.click(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" }));
      const editorOne = await screen.findByRole("dialog", { name: "编辑商品" });

      const minWearInput = within(editorOne).getByLabelText("配置最小磨损");
      await user.clear(minWearInput);
      await user.type(minWearInput, "0.12");

      const maxPriceInput = within(editorOne).getByLabelText("最高价格");
      await user.clear(maxPriceInput);
      await user.type(maxPriceInput, "188");
      await user.click(within(editorOne).getByLabelText("手动暂停"));
      await user.click(within(editorOne).getByRole("button", { name: "应用修改" }));

      await user.click(screen.getByRole("button", { name: "添加商品" }));
      const createPanel = await screen.findByRole("dialog", { name: "添加商品" });

      await user.type(
        within(createPanel).getByLabelText("商品链接"),
        "https://www.c5game.com/csgo/730/asset/1380979899390267000",
      );

      expect(
        harness.calls.some(
          (call) => call.method === "POST" && call.pathname === "/query-items/parse-url",
        ),
      ).toBe(false);
      expect(
        harness.calls.some(
          (call) => call.method === "POST" && call.pathname === "/query-items/fetch-detail",
        ),
      ).toBe(false);

      await user.click(within(createPanel).getByRole("button", { name: "查找商品信息" }));

      await waitFor(() => {
        expect(within(createPanel).getByLabelText("商品名称")).toHaveValue("M4A1-S | Printstream");
      });

      expect(within(createPanel).getByText("天然磨损范围 0.02 ~ 0.8")).toBeInTheDocument();
      expect(within(createPanel).getByLabelText("配置最小磨损")).toHaveValue(0.02);
      expect(within(createPanel).getByLabelText("new_api 专属目标")).toHaveValue(0);
      expect(within(createPanel).getByLabelText("fast_api 专属目标")).toHaveValue(0);
      expect(within(createPanel).getByLabelText("token 专属目标")).toHaveValue(0);

      const panelMaxWear = within(createPanel).getByLabelText("配置最大磨损");
      await user.clear(panelMaxWear);
      await user.type(panelMaxWear, "0.18");

      const panelMaxPrice = within(createPanel).getByLabelText("最高价格");
      await user.clear(panelMaxPrice);
      await user.type(panelMaxPrice, "888");

      const tokenAllocation = within(createPanel).getByLabelText("token 专属目标");
      await user.clear(tokenAllocation);
      await user.type(tokenAllocation, "2");

      await user.click(within(createPanel).getByRole("button", { name: "加入当前配置" }));

      expect(await screen.findByRole("region", { name: "商品 M4A1-S | Printstream" })).toBeInTheDocument();

      expect(screen.getByRole("button", { name: "保存到当前配置" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "保存到当前配置" }));

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "保存中..." })).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
      });

      expect(harness.calls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            body: {
              product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267000",
            },
            method: "POST",
            pathname: "/query-items/parse-url",
          }),
          expect.objectContaining({
            body: {
              external_item_id: "1380979899390267000",
              product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267000",
            },
            method: "POST",
            pathname: "/query-items/fetch-detail",
          }),
          expect.objectContaining({
            body: {
              detail_min_wear: 0.12,
              manual_paused: true,
              max_price: 188,
              detail_max_wear: 0.25,
              mode_allocations: {
                fast_api: 0,
                new_api: 1,
                token: 0,
              },
            },
            method: "PATCH",
            pathname: "/query-configs/cfg-1/items/item-1",
          }),
          expect.objectContaining({
            body: {
              detail_min_wear: 0.02,
              manual_paused: false,
              max_price: 888,
              detail_max_wear: 0.18,
              mode_allocations: {
                fast_api: 0,
                new_api: 0,
                token: 2,
              },
              product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267000",
            },
            method: "POST",
            pathname: "/query-configs/cfg-1/items",
          }),
        ]),
      );

      expect(
        consoleErrorSpy.mock.calls.some(([message]) => String(message).includes("Maximum update depth exceeded")),
      ).toBe(false);
    } finally {
      consoleErrorSpy.mockRestore();
    }
  });

  it("blocks save when dedicated allocations exceed the available capacity", async () => {
    const harness = createFetchHarness({
      capacityModes: {
        new_api: { mode_type: "new_api", available_account_count: 1 },
        fast_api: { mode_type: "fast_api", available_account_count: 1 },
        token: { mode_type: "token", available_account_count: 3 },
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemTwo = await screen.findByRole("region", { name: "商品 AWP | Asiimov" });
    await user.click(within(itemTwo).getByRole("button", { name: "修改价格 AWP | Asiimov" }));
    const editorTwo = await screen.findByRole("dialog", { name: "编辑商品" });
    const itemTwoNewApi = within(editorTwo).getByLabelText("new_api 专属目标");
    await user.clear(itemTwoNewApi);
    await user.type(itemTwoNewApi, "1");
    await user.click(within(editorTwo).getByRole("button", { name: "应用修改" }));

    const saveButton = screen.getByRole("button", { name: "保存到当前配置" });

    await user.click(saveButton);

    expect(screen.getByText("校验失败，无法保存")).toBeInTheDocument();
    expect(
      harness.calls.some(
        (call) => call.method === "PATCH" && call.pathname.startsWith("/query-configs/cfg-1/items/"),
      ),
    ).toBe(false);
    expect(
      harness.calls.some(
        (call) => call.method === "POST" && call.pathname === "/query-configs/cfg-1/items",
      ),
    ).toBe(false);
  });

  it("removes an item from the draft list and persists the deletion on save", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    expect(await screen.findByRole("region", { name: "商品 AK-47 | Redline" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "切换商品删除模式" }));
    await user.click(screen.getByRole("button", { name: "删除商品 AK-47 | Redline" }));

    await waitFor(() => {
      expect(screen.queryByRole("region", { name: "商品 AK-47 | Redline" })).not.toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "保存到当前配置" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "保存到当前配置" }));

    await waitFor(() => {
      expect(
        harness.calls.some(
          (call) => call.method === "DELETE" && call.pathname === "/query-configs/cfg-1/items/item-1",
        ),
      ).toBe(true);
    });
  });

  it("prompts before leaving the page and saves when the user chooses save", async () => {
    const harness = createFetchHarness({ saveDelayMs: 40 });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    await user.click(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" }));
    const editorOne = await screen.findByRole("dialog", { name: "编辑商品" });
    const maxPriceInput = within(editorOne).getByLabelText("最高价格");
    await user.clear(maxPriceInput);
    await user.type(maxPriceInput, "233");
    await user.click(within(editorOne).getByRole("button", { name: "应用修改" }));

    await user.click(screen.getByRole("button", { name: "账号中心" }));

    const leaveDialog = await screen.findByRole("dialog", { name: "未保存修改" });
    expect(within(leaveDialog).getByText("当前修改尚未保存，离开前选择保存或直接丢弃。")).toBeInTheDocument();

    await user.click(within(leaveDialog).getByRole("button", { name: "保存" }));

    await waitFor(() => {
      expect(screen.getByText("C5 账号中心")).toBeInTheDocument();
    });

    expect(
      harness.calls.some(
        (call) => call.method === "PATCH" && call.pathname === "/query-configs/cfg-1/items/item-1",
      ),
    ).toBe(true);
  });

  it("prompts before leaving the page and discards local edits when the user chooses not to save", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    await user.click(within(itemOne).getByRole("button", { name: "修改价格 AK-47 | Redline" }));
    const editorOne = await screen.findByRole("dialog", { name: "编辑商品" });
    const maxPriceInput = within(editorOne).getByLabelText("最高价格");
    await user.clear(maxPriceInput);
    await user.type(maxPriceInput, "211");
    await user.click(within(editorOne).getByRole("button", { name: "应用修改" }));

    await user.click(screen.getByRole("button", { name: "扫货系统" }));

    const leaveDialog = await screen.findByRole("dialog", { name: "未保存修改" });
    await user.click(within(leaveDialog).getByRole("button", { name: "不保存" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "开始扫货" })).toBeInTheDocument();
    });

    expect(
      harness.calls.some(
        (call) => call.method === "PATCH" && call.pathname === "/query-configs/cfg-1/items/item-1",
      ),
    ).toBe(false);
  });
});
