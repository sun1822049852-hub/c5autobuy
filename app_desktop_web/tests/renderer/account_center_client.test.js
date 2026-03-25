import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


describe("account center client", () => {
  it("loads account center rows from bootstrap api base url", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ account_id: "a-1", display_name: "账号 A" }],
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const rows = await client.listAccountCenterAccounts();

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/account-center/accounts",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(rows).toEqual([{ account_id: "a-1", display_name: "账号 A" }]);
  });

  it("loads and updates global query settings", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          modes: [
            {
              mode_type: "new_api",
              enabled: true,
              window_enabled: false,
              start_hour: 0,
              start_minute: 0,
              end_hour: 0,
              end_minute: 0,
              base_cooldown_min: 1.0,
              base_cooldown_max: 1.0,
              random_delay_enabled: false,
              random_delay_min: 0.0,
              random_delay_max: 0.0,
              created_at: "2026-03-22T12:00:00",
              updated_at: "2026-03-22T12:00:00",
            },
          ],
          warnings: [],
          updated_at: "2026-03-22T12:00:00",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          modes: [],
          warnings: ["浏览器查询器基础冷却低于 10 秒，封号风险极高"],
          updated_at: "2026-03-22T12:05:00",
        }),
      });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const settings = await client.getQuerySettings();
    const updated = await client.updateQuerySettings({
      modes: [
        {
          mode_type: "token",
          enabled: true,
          window_enabled: false,
          start_hour: 0,
          start_minute: 0,
          end_hour: 0,
          end_minute: 0,
          base_cooldown_min: 9.0,
          base_cooldown_max: 10.0,
          random_delay_enabled: false,
          random_delay_min: 0.0,
          random_delay_max: 0.0,
        },
      ],
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/query-settings",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/query-settings",
      expect.objectContaining({
        method: "PUT",
      }),
    );
    expect(settings.updated_at).toBe("2026-03-22T12:00:00");
    expect(updated.warnings).toEqual(["浏览器查询器基础冷却低于 10 秒，封号风险极高"]);
  });
});
