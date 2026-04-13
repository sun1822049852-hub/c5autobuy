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


function buildSecondaryConfigDetail() {
  return {
    config_id: "cfg-2",
    name: "夜刀配置",
    description: "夜间轮询",
    enabled: true,
    created_at: "2026-03-19T10:10:00",
    updated_at: "2026-03-19T10:10:00",
    mode_settings: [],
    items: [
      {
        query_item_id: "item-9",
        config_id: "cfg-2",
        product_url: "https://www.c5game.com/csgo/730/asset/1380979899390267999",
        external_item_id: "1380979899390267999",
        item_name: "Desert Eagle | Blaze",
        market_hash_name: "Desert Eagle | Blaze (Factory New)",
        min_wear: 0.0,
        max_wear: 0.08,
        detail_min_wear: 0.0,
        detail_max_wear: 0.03,
        max_price: 1999,
        last_market_price: 1888.88,
        last_detail_sync_at: "2026-03-19T10:11:00",
        manual_paused: false,
        mode_allocations: buildModeAllocations({ token: 1 }),
        sort_order: 0,
        created_at: "2026-03-19T10:10:00",
        updated_at: "2026-03-19T10:10:00",
      },
    ],
  };
}


function buildApplyConfigRuntimeStatus(detail) {
  return {
    running: true,
    config_id: "cfg-1",
    config_name: detail.name,
    message: "运行中",
    account_count: 3,
    started_at: "2026-03-19T11:00:00",
    stopped_at: null,
    total_query_count: 0,
    total_found_count: 0,
    modes: {},
    group_rows: [],
    recent_events: [],
    item_rows: detail.items.map((item) => ({
      query_item_id: item.query_item_id,
      item_name: item.item_name,
      max_price: item.max_price,
      min_wear: item.min_wear,
      max_wear: item.max_wear,
      detail_min_wear: item.detail_min_wear,
      detail_max_wear: item.detail_max_wear,
      manual_paused: item.manual_paused,
      query_count: 0,
      modes: {},
    })),
  };
}


function createFetchHarness({
  capacityModes = {
    new_api: { mode_type: "new_api", available_account_count: 2 },
    fast_api: { mode_type: "fast_api", available_account_count: 1 },
    token: { mode_type: "token", available_account_count: 3 },
  },
  applyConfigRuntimeStatus = null,
  runtimeStatus = buildRuntimeStatus(),
  saveDelayMs = 0,
  secondaryDetail = null,
} = {}) {
  let detail = buildConfigDetail();
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
      return jsonResponse(
        [detail, secondaryDetail]
          .filter(Boolean)
          .map((configDetail) => ({
            config_id: configDetail.config_id,
            name: configDetail.name,
            description: configDetail.description,
            enabled: configDetail.enabled,
            created_at: configDetail.created_at,
            updated_at: configDetail.updated_at,
            items: [],
            mode_settings: [],
          })),
      );
    }
    if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
      return jsonResponse({ modes: capacityModes });
    }
    if (url.pathname === "/query-runtime/status" && method === "GET") {
      return jsonResponse(runtimeStatus);
    }
    const detailMatch = url.pathname.match(/^\/query-configs\/([^/]+)$/);
    if (detailMatch && method === "GET") {
      const configId = detailMatch[1];
      if (configId === detail.config_id) {
        return jsonResponse(detail);
      }
      if (secondaryDetail && configId === secondaryDetail.config_id) {
        return jsonResponse(secondaryDetail);
      }
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

    if (url.pathname === "/query-runtime/configs/cfg-1/apply-config" && method === "POST") {
      const nextRuntimeStatus = typeof applyConfigRuntimeStatus === "function"
        ? applyConfigRuntimeStatus(detail)
        : (applyConfigRuntimeStatus || buildApplyConfigRuntimeStatus(detail));
      return delayedJsonResponse(nextRuntimeStatus, 200, saveDelayMs);
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


function getItemRow(itemName) {
  return screen.getByRole("region", { name: `商品 ${itemName}` });
}


async function openPriceDialog(user, itemName) {
  const itemRow = getItemRow(itemName);
  await user.click(within(itemRow).getByRole("button", { name: `修改扫货价 ${itemName}` }));
  return screen.findByRole("dialog", { name: "修改扫货价" });
}


async function openWearDialog(user, itemName) {
  const itemRow = getItemRow(itemName);
  await user.click(within(itemRow).getByRole("button", { name: `修改磨损 ${itemName}` }));
  return screen.findByRole("dialog", { name: "修改磨损" });
}


async function openAllocationDialog(user, itemName, modeType) {
  const itemRow = getItemRow(itemName);
  await user.click(within(itemRow).getByRole("button", { name: `修改 ${modeType} ${itemName}` }));
  return screen.findByRole("dialog", { name: `修改 ${modeType} 分配` });
}


async function closeDialog(user, dialog) {
  await user.click(within(dialog).getByRole("button", { name: "关闭" }));
  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: dialog.getAttribute("aria-label") || "" })).not.toBeInTheDocument();
  });
}


async function setPriceDraft(user, itemName, value) {
  const dialog = await openPriceDialog(user, itemName);
  const input = within(dialog).getByLabelText("扫货价");
  await user.clear(input);
  await user.type(input, value);
  await closeDialog(user, dialog);
}


async function setWearDraft(user, itemName, { minWear, maxWear }) {
  const dialog = await openWearDialog(user, itemName);
  if (minWear !== undefined) {
    const minWearInput = within(dialog).getByLabelText("配置最小磨损");
    await user.clear(minWearInput);
    await user.type(minWearInput, minWear);
  }
  if (maxWear !== undefined) {
    const maxWearInput = within(dialog).getByLabelText("配置最大磨损");
    await user.clear(maxWearInput);
    await user.type(maxWearInput, maxWear);
  }
  await closeDialog(user, dialog);
}


async function setAllocationDraft(user, itemName, modeType, value) {
  const dialog = await openAllocationDialog(user, itemName, modeType);
  const input = within(dialog).getByLabelText(`${modeType} 专属目标`);
  await user.clear(input);
  await user.type(input, value);
  await closeDialog(user, dialog);
}


async function toggleManualPause(user, itemName) {
  const itemRow = getItemRow(itemName);
  await user.click(within(itemRow).getByRole("button", { name: `切换手动暂停 ${itemName}` }));
}


describe("query system editing", () => {
  it("renders item rows with single-item dialogs and recalculates remaining dedicated capacity", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    const itemTwo = getItemRow("AWP | Asiimov");

    expect(within(itemOne).queryByRole("button", { name: "查看市场价 AK-47 | Redline" })).not.toBeInTheDocument();
    expect(within(itemOne).getByText("188.88")).toBeInTheDocument();
    expect(within(itemOne).getByRole("button", { name: "修改扫货价 AK-47 | Redline" })).toHaveTextContent("199");
    expect(within(itemOne).getByRole("button", { name: "修改磨损 AK-47 | Redline" })).toHaveTextContent("0.1 ~ 0.25");
    expect(within(itemOne).getByRole("button", { name: "修改 new_api AK-47 | Redline" })).toHaveTextContent("专属中 1/1");
    expect(within(itemTwo).queryByRole("button", { name: "查看市场价 AWP | Asiimov" })).not.toBeInTheDocument();
    expect(within(itemTwo).getByText("955.55")).toBeInTheDocument();
    expect(within(itemTwo).getByRole("button", { name: "修改扫货价 AWP | Asiimov" })).toHaveTextContent("999");
    expect(within(itemTwo).getByRole("button", { name: "修改 fast_api AWP | Asiimov" })).toHaveTextContent("无可用账号 0/1");
    const itemThree = getItemRow("M4A1-S | Blue Phosphor");
    expect(within(itemThree).getByRole("button", { name: "修改 new_api M4A1-S | Blue Phosphor" })).toHaveTextContent("手动暂停");
    expect(within(itemThree).getByRole("button", { name: "修改 token M4A1-S | Blue Phosphor" })).toHaveTextContent("手动暂停");
    expect(within(itemOne).getByRole("button", { name: "切换手动暂停 AK-47 | Redline" })).toBeInTheDocument();

    const priceDialog = await openPriceDialog(user, "AK-47 | Redline");
    expect(within(priceDialog).getByLabelText("市场价")).toHaveValue("188.88");
    expect(within(priceDialog).getByLabelText("扫货价")).toHaveValue(199);
    expect(within(priceDialog).queryByLabelText("配置最小磨损")).not.toBeInTheDocument();
    expect(within(priceDialog).queryByLabelText("new_api 专属目标")).not.toBeInTheDocument();
    await closeDialog(user, priceDialog);

    const wearDialog = await openWearDialog(user, "AK-47 | Redline");
    expect(within(wearDialog).getByText("天然磨损范围 0.1 ~ 0.7")).toBeInTheDocument();
    expect(within(wearDialog).getByLabelText("配置最小磨损")).toHaveValue(0.1);
    expect(within(wearDialog).getByLabelText("配置最大磨损")).toHaveValue(0.25);
    expect(within(wearDialog).queryByLabelText("扫货价")).not.toBeInTheDocument();
    expect(within(wearDialog).queryByLabelText("new_api 专属目标")).not.toBeInTheDocument();
    await closeDialog(user, wearDialog);

    const newApiDialog = await openAllocationDialog(user, "AWP | Asiimov", "new_api");
    expect(within(newApiDialog).getByLabelText("new_api 专属目标")).toHaveValue(0);
    expect(within(newApiDialog).getByText("new_api 还可分配 1")).toBeInTheDocument();
    expect(within(newApiDialog).queryByLabelText("fast_api 专属目标")).not.toBeInTheDocument();
    await user.clear(within(newApiDialog).getByLabelText("new_api 专属目标"));
    await user.type(within(newApiDialog).getByLabelText("new_api 专属目标"), "1");
    await closeDialog(user, newApiDialog);

    expect(within(itemTwo).getByRole("button", { name: "修改 new_api AWP | Asiimov" })).toHaveTextContent("无可用账号 0/1");

    const editorOneAgain = await openAllocationDialog(user, "AK-47 | Redline", "new_api");
    expect(within(editorOneAgain).getByText("new_api 还可分配 1")).toBeInTheDocument();
    await closeDialog(user, editorOneAgain);
  });

  it("toggles manual pause inline and swaps the token-side control with delete mode", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemOne = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    expect(within(itemOne).getByRole("button", { name: "切换手动暂停 AK-47 | Redline" })).toBeInTheDocument();

    await toggleManualPause(user, "AK-47 | Redline");

    expect(within(itemOne).getByRole("button", { name: "修改 new_api AK-47 | Redline" })).toHaveTextContent("手动暂停");
    expect(within(itemOne).getByRole("button", { name: "修改 fast_api AK-47 | Redline" })).toHaveTextContent("手动暂停");
    expect(within(itemOne).getByRole("button", { name: "修改 token AK-47 | Redline" })).toHaveTextContent("手动暂停");
    expect(screen.getByRole("button", { name: "保存到当前配置" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "切换商品删除模式" }));

    expect(within(itemOne).queryByRole("button", { name: "切换手动暂停 AK-47 | Redline" })).not.toBeInTheDocument();
    expect(within(itemOne).getByRole("button", { name: "删除商品 AK-47 | Redline" })).toHaveTextContent("-");
  });

  it("adds a draft item from the centered create dialog and saves both existing and new items", { timeout: 15000 }, async () => {
    const harness = createFetchHarness({ saveDelayMs: 40 });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    try {
      await openQuerySystem(user);

      await setWearDraft(user, "AK-47 | Redline", { minWear: "0.12" });
      await setPriceDraft(user, "AK-47 | Redline", "188");
      await toggleManualPause(user, "AK-47 | Redline");

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

      const panelMaxPrice = within(createPanel).getByLabelText("扫货价");
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

      expect(
        screen.getByText("新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。"),
      ).toBeInTheDocument();
      expect(
        within(screen.getByRole("region", { name: "商品 AK-47 | Redline" })).getByRole("button", { name: "修改 new_api AK-47 | Redline" }),
      ).toHaveTextContent("手动暂停");

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
          expect.objectContaining({
            body: {},
            method: "POST",
            pathname: "/query-runtime/configs/cfg-1/apply-config",
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

  it("applies the returned runtime snapshot immediately after unpausing a running item", async () => {
    const staleRuntimeStatus = buildRuntimeStatus();
    staleRuntimeStatus.item_rows = staleRuntimeStatus.item_rows.map((row) => (
      row.query_item_id !== "item-3"
        ? row
        : {
          ...row,
          manual_paused: true,
          modes: {
            new_api: {
              mode_type: "new_api",
              target_dedicated_count: 1,
              actual_dedicated_count: 0,
              status: "manual_paused",
              status_message: "手动暂停",
            },
            token: {
              mode_type: "token",
              target_dedicated_count: 1,
              actual_dedicated_count: 0,
              status: "manual_paused",
              status_message: "手动暂停",
            },
          },
        }
    ));

    const harness = createFetchHarness({
      runtimeStatus: staleRuntimeStatus,
      applyConfigRuntimeStatus(detail) {
        return {
          ...buildApplyConfigRuntimeStatus(detail),
          item_rows: detail.items.map((item) => (
            item.query_item_id !== "item-3"
              ? {
                query_item_id: item.query_item_id,
                item_name: item.item_name,
                max_price: item.max_price,
                min_wear: item.min_wear,
                max_wear: item.max_wear,
                detail_min_wear: item.detail_min_wear,
                detail_max_wear: item.detail_max_wear,
                manual_paused: item.manual_paused,
                query_count: 0,
                modes: {},
              }
              : {
                query_item_id: item.query_item_id,
                item_name: item.item_name,
                max_price: item.max_price,
                min_wear: item.min_wear,
                max_wear: item.max_wear,
                detail_min_wear: item.detail_min_wear,
                detail_max_wear: item.detail_max_wear,
                manual_paused: false,
                query_count: 0,
                modes: {
                  new_api: {
                    mode_type: "new_api",
                    target_dedicated_count: 1,
                    actual_dedicated_count: 1,
                    status: "dedicated",
                    status_message: "专属中 1/1",
                  },
                  token: {
                    mode_type: "token",
                    target_dedicated_count: 1,
                    actual_dedicated_count: 0,
                    status: "no_capacity",
                    status_message: "无可用账号 0/1",
                  },
                },
              }
          )),
        };
      },
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    const itemThree = await screen.findByRole("region", { name: "商品 M4A1-S | Blue Phosphor" });
    expect(within(itemThree).getByRole("button", { name: "修改 new_api M4A1-S | Blue Phosphor" })).toHaveTextContent("手动暂停");
    await toggleManualPause(user, "M4A1-S | Blue Phosphor");

    await user.click(screen.getByRole("button", { name: "保存到当前配置" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    });

    const itemThreeSaved = screen.getByRole("region", { name: "商品 M4A1-S | Blue Phosphor" });
    expect(within(itemThreeSaved).getByRole("button", { name: "修改 new_api M4A1-S | Blue Phosphor" })).toHaveTextContent("专属中 1/1");
    expect(within(itemThreeSaved).getByRole("button", { name: "修改 token M4A1-S | Blue Phosphor" })).toHaveTextContent("无可用账号 0/1");
  });

  it("clears the running-save notice once the draft changes again", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    await setPriceDraft(user, "AK-47 | Redline", "188");

    await user.click(screen.getByRole("button", { name: "保存到当前配置" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    });
    expect(
      screen.getByText("新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。"),
    ).toBeInTheDocument();

    await setPriceDraft(user, "AK-47 | Redline", "190");

    expect(screen.queryByText("新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存到当前配置" })).toBeInTheDocument();
  });

  it("clears the running-save notice when switching to another config", async () => {
    const harness = createFetchHarness({
      secondaryDetail: buildSecondaryConfigDetail(),
    });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    await setPriceDraft(user, "AK-47 | Redline", "188");

    await user.click(screen.getByRole("button", { name: "保存到当前配置" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    });
    expect(
      screen.getByText("新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。"),
    ).toBeInTheDocument();

    const nav = screen.getByRole("navigation", { name: "配置管理导航" });
    await user.click(within(nav).getByRole("button", { name: /^夜刀配置/ }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "夜刀配置" })).toBeInTheDocument();
    });

    expect(screen.queryByText("新配置已生效，仅影响后续新命中；已入队或已派发的旧扫货任务会按旧快照执行完毕。")).not.toBeInTheDocument();
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

    await setAllocationDraft(user, "AWP | Asiimov", "new_api", "1");

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

  it("applies the whole runtime config when deleting all items from a running config", async () => {
    const harness = createFetchHarness();
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    await user.click(screen.getByRole("button", { name: "切换商品删除模式" }));
    await user.click(screen.getByRole("button", { name: "删除商品 AK-47 | Redline" }));
    await user.click(screen.getByRole("button", { name: "删除商品 AWP | Asiimov" }));
    await user.click(screen.getByRole("button", { name: "删除商品 M4A1-S | Blue Phosphor" }));

    await waitFor(() => {
      expect(screen.queryByRole("region", { name: "商品 AK-47 | Redline" })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "商品 AWP | Asiimov" })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "商品 M4A1-S | Blue Phosphor" })).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "保存到当前配置" }));

    await waitFor(() => {
      expect(
        harness.calls.some(
          (call) => call.method === "POST" && call.pathname === "/query-runtime/configs/cfg-1/apply-config",
        ),
      ).toBe(true);
    });
  });

  it("prompts before leaving the page and saves when the user chooses save", async () => {
    const harness = createFetchHarness({ saveDelayMs: 40 });
    installDesktopApp(harness.fetchImpl);
    const user = userEvent.setup();

    await openQuerySystem(user);

    await setPriceDraft(user, "AK-47 | Redline", "233");

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

    await setPriceDraft(user, "AK-47 | Redline", "211");

    await user.click(screen.getByRole("button", { name: "扫货系统" }));

    const leaveDialog = await screen.findByRole("dialog", { name: "未保存修改" });
    await user.click(within(leaveDialog).getByRole("button", { name: "不保存" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "开始扫货" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "配置管理" }));
    const itemOneAgain = await screen.findByRole("region", { name: "商品 AK-47 | Redline" });
    expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    expect(within(itemOneAgain).getByRole("button", { name: "修改扫货价 AK-47 | Redline" })).toHaveTextContent("199");

    expect(
      harness.calls.some(
        (call) => call.method === "PATCH" && call.pathname === "/query-configs/cfg-1/items/item-1",
      ),
    ).toBe(false);
  });
});
