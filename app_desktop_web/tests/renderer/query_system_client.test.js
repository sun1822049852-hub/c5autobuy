import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
  });
}


describe("query system client", () => {
  it("calls query config and runtime endpoints with expected payloads", async () => {
    const calls = [];
    const fetchImpl = vi.fn(async (input, options = {}) => {
      const url = new URL(input);
      const method = String(options.method ?? "GET").toUpperCase();
      const body = typeof options.body === "string" ? JSON.parse(options.body) : null;
      calls.push({
        body,
        method,
        pathname: url.pathname,
      });

      if (url.pathname === "/query-configs" && method === "GET") {
        return jsonResponse([{ config_id: "cfg-1", name: "配置 A" }]);
      }
      if (url.pathname === "/query-configs/capacity-summary" && method === "GET") {
        return jsonResponse({ modes: { new_api: { mode_type: "new_api", available_account_count: 2 } } });
      }
      if (url.pathname === "/query-configs/cfg-1" && method === "GET") {
        return jsonResponse({ config_id: "cfg-1", name: "配置 A", items: [], mode_settings: [] });
      }
      if (url.pathname === "/query-configs" && method === "POST") {
        return jsonResponse({ config_id: "cfg-2", name: body.name, description: body.description }, 201);
      }
      if (url.pathname === "/query-configs/cfg-2" && method === "DELETE") {
        return jsonResponse({}, 204);
      }
      if (url.pathname === "/query-configs/cfg-1/items" && method === "POST") {
        return jsonResponse({ query_item_id: "item-1", product_url: body.product_url }, 201);
      }
      if (url.pathname === "/query-configs/cfg-1/items/item-1" && method === "PATCH") {
        return jsonResponse({
          query_item_id: "item-1",
          detail_min_wear: body.detail_min_wear,
          detail_max_wear: body.detail_max_wear,
          max_price: body.max_price,
        });
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
      if (url.pathname === "/query-runtime/status" && method === "GET") {
        return jsonResponse({ running: false, item_rows: [] });
      }
      if (url.pathname === "/query-runtime/start" && method === "POST") {
        return jsonResponse({ running: true, config_id: body.config_id });
      }
      if (url.pathname === "/query-runtime/stop" && method === "POST") {
        return jsonResponse({ running: false });
      }

      throw new Error(`Unhandled request: ${method} ${url.pathname}`);
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const list = await client.listQueryConfigs();
    const detail = await client.getQueryConfig("cfg-1");
    const capacity = await client.getQueryCapacitySummary();
    const runtimeStatus = await client.getQueryRuntimeStatus();
    const started = await client.startQueryRuntime("cfg-1");
    const stopped = await client.stopQueryRuntime();
    const created = await client.createQueryConfig({ name: "配置 B", description: "desc" });
    await client.deleteQueryConfig("cfg-2");
    const createdItem = await client.addQueryItem("cfg-1", {
      product_url: "https://www.c5game.com/item/1",
      detail_min_wear: 0.02,
      detail_max_wear: 0.18,
    });
    const updatedItem = await client.updateQueryItem("cfg-1", "item-1", {
      detail_min_wear: 0.05,
      detail_max_wear: 0.15,
      max_price: 123.45,
    });
    const parsedItem = await client.parseQueryItemUrl("https://www.c5game.com/item/1380979899390267000");
    const fetchedDetail = await client.fetchQueryItemDetail({
      product_url: parsedItem.product_url,
      external_item_id: parsedItem.external_item_id,
    });

    expect(list).toEqual([{ config_id: "cfg-1", name: "配置 A" }]);
    expect(detail.config_id).toBe("cfg-1");
    expect(capacity.modes.new_api.available_account_count).toBe(2);
    expect(runtimeStatus.running).toBe(false);
    expect(started).toEqual({ running: true, config_id: "cfg-1" });
    expect(stopped).toEqual({ running: false });
    expect(created.config_id).toBe("cfg-2");
    expect(createdItem.query_item_id).toBe("item-1");
    expect(updatedItem.detail_min_wear).toBe(0.05);
    expect(updatedItem.detail_max_wear).toBe(0.15);
    expect(updatedItem.max_price).toBe(123.45);
    expect(parsedItem.external_item_id).toBe("1380979899390267000");
    expect(fetchedDetail.item_name).toBe("M4A1-S | Printstream");
    expect(fetchedDetail.max_wear).toBe(0.8);

    expect(calls).toEqual([
      { body: null, method: "GET", pathname: "/query-configs" },
      { body: null, method: "GET", pathname: "/query-configs/cfg-1" },
      { body: null, method: "GET", pathname: "/query-configs/capacity-summary" },
      { body: null, method: "GET", pathname: "/query-runtime/status" },
      { body: { config_id: "cfg-1" }, method: "POST", pathname: "/query-runtime/start" },
      { body: {}, method: "POST", pathname: "/query-runtime/stop" },
      { body: { description: "desc", name: "配置 B" }, method: "POST", pathname: "/query-configs" },
      { body: null, method: "DELETE", pathname: "/query-configs/cfg-2" },
      {
        body: {
          detail_max_wear: 0.18,
          detail_min_wear: 0.02,
          product_url: "https://www.c5game.com/item/1",
        },
        method: "POST",
        pathname: "/query-configs/cfg-1/items",
      },
      {
        body: {
          detail_max_wear: 0.15,
          detail_min_wear: 0.05,
          max_price: 123.45,
        },
        method: "PATCH",
        pathname: "/query-configs/cfg-1/items/item-1",
      },
      { body: { product_url: "https://www.c5game.com/item/1380979899390267000" }, method: "POST", pathname: "/query-items/parse-url" },
      {
        body: {
          external_item_id: "1380979899390267000",
          product_url: "https://www.c5game.com/item/1380979899390267000",
        },
        method: "POST",
        pathname: "/query-items/fetch-detail",
      },
    ]);
  });
});
