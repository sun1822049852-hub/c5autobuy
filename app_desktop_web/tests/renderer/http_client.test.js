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

  it("maps abort-like fetch errors caused by internal timeout to the timeout error", async () => {
    vi.useFakeTimers();

    const fetchImpl = vi.fn((_url, options = {}) => new Promise((_, reject) => {
      options.signal?.addEventListener("abort", () => {
        reject(new Error("signal is aborted without reason"));
      }, { once: true });
    }));
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
