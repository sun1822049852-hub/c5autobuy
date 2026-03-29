import { afterEach, describe, expect, it, vi } from "vitest";

import { createHttpClient } from "../../src/api/http.js";


describe("http client", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("times out hanging requests instead of waiting forever", async () => {
    vi.useFakeTimers();

    const fetchImpl = vi.fn(() => new Promise(() => {}));
    const client = createHttpClient({
      baseUrl: "http://127.0.0.1:8123",
      fetchImpl,
      requestTimeoutMs: 50,
    });

    const pending = client.getJson("/health");
    const rejection = expect(pending).rejects.toMatchObject({
      isTimeout: true,
      method: "GET",
      path: "/health",
      status: 408,
    });

    await vi.advanceTimersByTimeAsync(60);

    await rejection;
  });
});
