import { describe, expect, it, vi } from "vitest";

import { persistQueryConfigDraft } from "../../src/features/query-system/query_system_persistence.js";


describe("query system persistence", () => {
  it("deletes removed items, updates existing items, and adds new items with the right payloads", async () => {
    const operations = [];
    const client = {
      addQueryItem: vi.fn(async (...args) => {
        operations.push(["add", ...args]);
      }),
      deleteQueryItem: vi.fn(async (...args) => {
        operations.push(["delete", ...args]);
      }),
      updateQueryItem: vi.fn(async (...args) => {
        operations.push(["update", ...args]);
      }),
    };

    await persistQueryConfigDraft({
      client,
      sourceConfig: {
        config_id: "cfg-1",
        items: [
          {
            query_item_id: "item-removed",
            product_url: "https://example.com/removed",
            detail_min_wear: 0.1,
            detail_max_wear: 0.2,
            max_price: 111,
            manual_paused: false,
            mode_allocations: [
              { mode_type: "new_api", target_dedicated_count: 1 },
            ],
          },
          {
            query_item_id: "item-existing",
            product_url: "https://example.com/existing",
            detail_min_wear: 0.2,
            detail_max_wear: 0.3,
            max_price: 222,
            manual_paused: false,
            mode_allocations: [
              { mode_type: "fast_api", target_dedicated_count: 1 },
            ],
          },
        ],
      },
      draftConfig: {
        config_id: "cfg-1",
        items: [
          {
            query_item_id: "item-existing",
            product_url: "https://example.com/existing",
            detail_min_wear: "0.25",
            detail_max_wear: "0.35",
            max_price: "333",
            manual_paused: true,
            mode_allocations: [
              { mode_type: "fast_api", target_dedicated_count: "2" },
            ],
          },
          {
            query_item_id: "draft-item-1",
            product_url: "https://example.com/new",
            detail_min_wear: "0.01",
            detail_max_wear: "0.05",
            max_price: "444",
            manual_paused: false,
            mode_allocations: [
              { mode_type: "token", target_dedicated_count: "1" },
            ],
            isNew: true,
          },
        ],
      },
    });

    expect(operations).toEqual([
      ["delete", "cfg-1", "item-removed"],
      ["update", "cfg-1", "item-existing", {
        detail_min_wear: 0.25,
        detail_max_wear: 0.35,
        max_price: 333,
        manual_paused: true,
        mode_allocations: {
          new_api: 0,
          fast_api: 2,
          token: 0,
        },
      }],
      ["add", "cfg-1", {
        product_url: "https://example.com/new",
        detail_min_wear: 0.01,
        detail_max_wear: 0.05,
        max_price: 444,
        manual_paused: false,
        mode_allocations: {
          new_api: 0,
          fast_api: 0,
          token: 1,
        },
      }],
    ]);
  });
});
