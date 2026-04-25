import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


describe("account center client", () => {
  it("loads app bootstrap snapshot from the remote shell endpoint", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 3, query_system: {}, purchase_system: {} }),
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const payload = await client.getAppBootstrap();

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/app/bootstrap",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(payload).toEqual({ version: 3, query_system: {}, purchase_system: {} });
  });

  it("supports shell/full bootstrap scopes for staged hydration", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ version: 3, program_access: { mode: "local_pass_through" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ version: 3, query_system: {}, purchase_system: {} }),
      });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const shellPayload = await client.getAppBootstrapShell();
    const fullPayload = await client.getAppBootstrapFull();

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/app/bootstrap?scope=shell",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/app/bootstrap",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(shellPayload).toEqual({ version: 3, program_access: { mode: "local_pass_through" } });
    expect(fullPayload).toEqual({ version: 3, query_system: {}, purchase_system: {} });
  });

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

  it("loads a single account by id", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ account_id: "a-1", display_name: "账号 A" }),
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const account = await client.getAccount("a-1");

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/accounts/a-1",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(account).toEqual({ account_id: "a-1", display_name: "账号 A" });
  });

  it("streams account updates through websocket", async () => {
    class FakeWebSocket {
      static instances = [];

      constructor(url) {
        this.url = url;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        FakeWebSocket.instances.push(this);
        queueMicrotask(() => this.onopen?.());
      }

      emit(payload) {
        this.onmessage?.({ data: JSON.stringify(payload) });
      }

      close() {
        this.onclose?.();
      }
    }

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl: vi.fn(),
      WebSocketImpl: FakeWebSocket,
    });

    const iterator = client.watchAccountUpdates();
    const nextPromise = iterator.next();
    await Promise.resolve();
    expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8123/ws/accounts/updates");
    FakeWebSocket.instances[0].emit({
      account_id: "a-1",
      event: "write_account",
      updated_at: "2026-03-27T20:00:00",
      payload: { api_key: "api-1" },
    });

    const next = await nextPromise;
    expect(next.value).toEqual({
      account_id: "a-1",
      event: "write_account",
      updated_at: "2026-03-27T20:00:00",
      payload: { api_key: "api-1" },
    });
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

  it("updates account query modes through the dedicated query-modes route", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        new_api_enabled: false,
        fast_api_enabled: false,
        token_enabled: false,
        api_query_disabled_reason: "manual_disabled",
        browser_query_disabled_reason: "manual_disabled",
      }),
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const updated = await client.updateAccountQueryModes("a-1", {
      api_query_enabled: false,
      api_query_disabled_reason: "manual_disabled",
      browser_query_enabled: false,
      browser_query_disabled_reason: "manual_disabled",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/accounts/a-1/query-modes",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          api_query_enabled: false,
          api_query_disabled_reason: "manual_disabled",
          browser_query_enabled: false,
          browser_query_disabled_reason: "manual_disabled",
        }),
      }),
    );
    expect(updated).toEqual({
      new_api_enabled: false,
      fast_api_enabled: false,
      token_enabled: false,
      api_query_disabled_reason: "manual_disabled",
      browser_query_disabled_reason: "manual_disabled",
    });
  });

});
