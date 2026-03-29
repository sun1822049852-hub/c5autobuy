import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


describe("purchase system client", () => {
  it("loads purchase runtime status", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ running: false, message: "未运行" }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const status = await client.getPurchaseRuntimeStatus();

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/purchase-runtime/status",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(status).toEqual({ running: false, message: "未运行" });
  });

  it("starts and stops purchase runtime", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ running: true, message: "运行中" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ running: false, message: "未运行" }),
      });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const started = await client.startPurchaseRuntime("cfg-2");
    const stopped = await client.stopPurchaseRuntime();

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/purchase-runtime/start",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ config_id: "cfg-2" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/purchase-runtime/stop",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(started.running).toBe(true);
    expect(stopped.running).toBe(false);
  });

  it("updates account purchase config for purchase enablement", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        account_id: "a1",
        display_name: "购买账号-A",
        purchase_disabled: false,
        selected_steam_id: "steam-1",
      }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const updated = await client.updateAccountPurchaseConfig("a1", {
      purchase_disabled: false,
      selected_steam_id: "steam-1",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/accounts/a1/purchase-config",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          purchase_disabled: false,
          selected_steam_id: "steam-1",
        }),
      }),
    );
    expect(updated.purchase_disabled).toBe(false);
    expect(updated.selected_steam_id).toBe("steam-1");
  });

  it("applies the saved query item configuration to the current runtime", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "applied",
        message: "已保存，并已应用到当前运行配置",
        config_id: "cfg-2",
        query_item_id: "item-1",
      }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const response = await client.applyQueryItemRuntime("cfg-2", "item-1");

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/query-configs/cfg-2/items/item-1/apply-runtime",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(response).toEqual({
      status: "applied",
      message: "已保存，并已应用到当前运行配置",
      config_id: "cfg-2",
      query_item_id: "item-1",
    });
  });

  it("submits runtime manual allocation drafts for the purchase page", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        running: true,
        config_id: "cfg-2",
        config_name: "夜刀配置",
        message: "运行中",
      }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const response = await client.submitQueryRuntimeManualAllocations("cfg-2", {
      items: [
        {
          query_item_id: "item-1",
          mode_type: "new_api",
          target_actual_count: 2,
        },
      ],
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/query-runtime/configs/cfg-2/manual-assignments",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          items: [
            {
              query_item_id: "item-1",
              mode_type: "new_api",
              target_actual_count: 2,
            },
          ],
        }),
      }),
    );
    expect(response.running).toBe(true);
    expect(response.config_id).toBe("cfg-2");
  });

  it("loads and updates purchase ui preferences", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ selected_config_id: "cfg-1", updated_at: "2026-03-22T10:00:00" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ selected_config_id: "cfg-2", updated_at: "2026-03-22T10:05:00" }),
      });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const currentPreferences = await client.getPurchaseUiPreferences();
    const updatedPreferences = await client.updatePurchaseUiPreferences("cfg-2");

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/purchase-runtime/ui-preferences",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/purchase-runtime/ui-preferences",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ selected_config_id: "cfg-2" }),
      }),
    );
    expect(currentPreferences.selected_config_id).toBe("cfg-1");
    expect(updatedPreferences.selected_config_id).toBe("cfg-2");
  });

  it("loads and updates purchase runtime settings", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ per_batch_ip_fanout_limit: 1, updated_at: null }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ per_batch_ip_fanout_limit: 4, updated_at: "2026-03-29T12:00:00" }),
      });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const currentSettings = await client.getPurchaseRuntimeSettings();
    const updatedSettings = await client.updatePurchaseRuntimeSettings({
      per_batch_ip_fanout_limit: 4,
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/runtime-settings/purchase",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/runtime-settings/purchase",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ per_batch_ip_fanout_limit: 4 }),
      }),
    );
    expect(currentSettings.per_batch_ip_fanout_limit).toBe(1);
    expect(updatedSettings.per_batch_ip_fanout_limit).toBe(4);
  });

  it("loads query item stats with only the provided range params", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        range_mode: "range",
        start_date: "2026-03-21",
        end_date: "2026-03-22",
        items: [],
      }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const response = await client.getQueryItemStats({
      rangeMode: "range",
      startDate: "2026-03-21",
      endDate: "2026-03-22",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/stats/query-items?range_mode=range&start_date=2026-03-21&end_date=2026-03-22",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(response.range_mode).toBe("range");
  });

  it("loads account capability stats with day mode params", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        range_mode: "day",
        date: "2026-03-21",
        items: [],
      }),
    });
    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const response = await client.getAccountCapabilityStats({
      rangeMode: "day",
      date: "2026-03-21",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/stats/account-capability?range_mode=day&date=2026-03-21",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(response.range_mode).toBe("day");
  });
});
