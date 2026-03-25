import { describe, expect, it, vi } from "vitest";

import { createAccountCenterClient } from "../../src/api/account_center_client.js";


describe("diagnostics client", () => {
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
