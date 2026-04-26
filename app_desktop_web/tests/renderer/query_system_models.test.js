import { describe, expect, it } from "vitest";

import {
  buildStatusByMode,
  getConfigStatusText,
  normalizeConfig,
  serializeItemPayload,
  validateDraftConfig,
} from "../../src/features/query-system/query_system_models.js";


describe("query system models", () => {
  it("normalizes config items with detail wear defaults and full mode allocations", () => {
    const normalized = normalizeConfig({
      config_id: "cfg-1",
      items: [
        {
          query_item_id: "item-1",
          min_wear: 0.11,
          max_wear: 0.44,
          mode_allocations: [
            { mode_type: "new_api", target_dedicated_count: 2 },
          ],
        },
      ],
    });

    expect(normalized.items[0]).toMatchObject({
      detail_min_wear: 0.11,
      detail_max_wear: 0.44,
      mode_allocations: [
        { mode_type: "new_api", target_dedicated_count: 2 },
        { mode_type: "fast_api", target_dedicated_count: 0 },
        { mode_type: "token", target_dedicated_count: 0 },
      ],
    });
  });

  it("builds per-mode status using runtime rows and manual pause fallback", () => {
    expect(buildStatusByMode(
      {
        manual_paused: true,
        mode_allocations: [
          { mode_type: "new_api", target_dedicated_count: 1 },
        ],
      },
      null,
    ).new_api).toMatchObject({
      status: "manual_paused",
      status_message: "手动暂停",
      target_dedicated_count: 1,
    });

    expect(buildStatusByMode(
      {
        manual_paused: false,
        mode_allocations: [
          { mode_type: "fast_api", target_dedicated_count: 2 },
        ],
      },
      {
        modes: {
          fast_api: {
            mode_type: "fast_api",
            target_dedicated_count: 2,
            actual_dedicated_count: 1,
            status: "shared_pool",
            status_message: "共享池 1/2",
          },
        },
      },
    ).fast_api).toMatchObject({
      status: "shared_pool",
      status_message: "共享池 1/2",
      actual_dedicated_count: 1,
    });
  });

  it("keeps manual pause visible until a fresh runtime snapshot says otherwise", () => {
    expect(buildStatusByMode(
      {
        manual_paused: true,
        mode_allocations: [
          { mode_type: "new_api", target_dedicated_count: 1 },
        ],
      },
      {
        modes: {
          new_api: {
            mode_type: "new_api",
            target_dedicated_count: 1,
            actual_dedicated_count: 1,
            status: "shared_pool",
            status_message: "共享池 1/1",
          },
        },
      },
    ).new_api).toMatchObject({
      status: "manual_paused",
      status_message: "手动暂停",
      actual_dedicated_count: 0,
      target_dedicated_count: 1,
    });
  });

  it("validates draft allocations against available capacity", () => {
    expect(validateDraftConfig(
      {
        items: [
          {
            manual_paused: false,
            mode_allocations: [
              { mode_type: "new_api", target_dedicated_count: 2 },
            ],
          },
        ],
      },
      {
        new_api: { available_account_count: 1 },
        fast_api: { available_account_count: 0 },
        token: { available_account_count: 0 },
      },
    )).toEqual({
      valid: false,
      message: "校验失败，无法保存",
    });
  });

  it("serializes item payloads with numeric coercion and optional product url", () => {
    const item = {
      product_url: "https://example.com/item",
      detail_min_wear: "0.05",
      detail_max_wear: "0.18",
      max_price: "456.7",
      manual_paused: 0,
      mode_allocations: [
        { mode_type: "new_api", target_dedicated_count: "2" },
      ],
    };

    expect(serializeItemPayload(item)).toEqual({
      detail_min_wear: 0.05,
      detail_max_wear: 0.18,
      max_price: 456.7,
      manual_paused: false,
      mode_allocations: {
        new_api: 2,
        fast_api: 0,
        token: 0,
      },
    });

    expect(serializeItemPayload(item, { includeProductUrl: true })).toEqual({
      product_url: "https://example.com/item",
      detail_min_wear: 0.05,
      detail_max_wear: 0.18,
      max_price: 456.7,
      manual_paused: false,
      mode_allocations: {
        new_api: 2,
        fast_api: 0,
        token: 0,
      },
    });
  });

  it("derives config status text from save state and runtime ownership", () => {
    expect(getConfigStatusText({
      configId: "cfg-1",
      hasUnsavedChanges: true,
      isCurrentConfig: true,
      runtimeStatus: {
        running: false,
        config_id: null,
        message: "未运行",
      },
      saveError: "",
    })).toBe("未保存");

    expect(getConfigStatusText({
      configId: "cfg-1",
      hasUnsavedChanges: false,
      isCurrentConfig: false,
      runtimeStatus: {
        running: false,
        config_id: "cfg-1",
        message: "等待购买账号恢复",
      },
      saveError: "",
    })).toBe("等待账号");

    expect(getConfigStatusText({
      configId: "cfg-1",
      hasUnsavedChanges: false,
      isCurrentConfig: false,
      runtimeStatus: {
        running: false,
        config_id: "cfg-1",
        state: "waiting",
        message: "购买账号恢复中",
      },
      saveError: "",
    })).toBe("等待账号");
  });
});
