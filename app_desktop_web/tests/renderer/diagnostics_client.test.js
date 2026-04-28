import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


describe("diagnostics client", () => {
  it("streams sidebar diagnostics from the dedicated websocket endpoint", async () => {
    class FakeWebSocket {
      static instances = [];

      constructor(url) {
        this.url = url;
        FakeWebSocket.instances.push(this);
      }

      emit(payload) {
        this.onmessage?.({
          data: JSON.stringify(payload),
        });
      }
    }

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      WebSocketImpl: FakeWebSocket,
    });

    const nextSnapshot = client.watchSidebarDiagnosticsUpdates().next();

    expect(FakeWebSocket.instances[0].url).toBe("ws://127.0.0.1:8123/ws/diagnostics/sidebar");

    FakeWebSocket.instances[0].onopen?.();
    FakeWebSocket.instances[0].emit({
      summary: {},
      query: {},
      purchase: {},
      login_tasks: {},
      updated_at: "2026-03-25T20:00:00",
    });

    await expect(nextSnapshot).resolves.toEqual(
      expect.objectContaining({
        done: false,
        value: expect.objectContaining({
          updated_at: "2026-03-25T20:00:00",
        }),
      }),
    );
  });

  it("loads sidebar diagnostics from the aggregate endpoint", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        summary: {},
        query: {},
        purchase: {},
        login_tasks: {},
        updated_at: "2026-03-25T20:00:00",
      }),
    });

    const client = createAccountCenterClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    await client.getSidebarDiagnostics();

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/diagnostics/sidebar",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });
});
