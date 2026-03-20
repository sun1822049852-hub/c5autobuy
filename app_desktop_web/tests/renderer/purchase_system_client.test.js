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

    const started = await client.startPurchaseRuntime();
    const stopped = await client.stopPurchaseRuntime();

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/purchase-runtime/start",
      expect.objectContaining({
        method: "POST",
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
});
