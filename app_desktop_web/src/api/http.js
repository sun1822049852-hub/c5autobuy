function normalizeBaseUrl(baseUrl = "") {
  return String(baseUrl).replace(/\/+$/, "");
}


function buildUrl(baseUrl, path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizeBaseUrl(baseUrl)}${normalizedPath}`;
}


function buildHttpError({ message, method, path, status }) {
  const error = new Error(message || `HTTP ${status || "unknown"}`);
  error.method = method;
  error.path = path;
  error.responseText = message || "";
  error.status = status;
  return error;
}


function buildTimeoutError({ method, path, timeoutMs }) {
  const error = buildHttpError({
    message: `请求超时，请检查本地后端是否卡死 (${timeoutMs}ms)`,
    method,
    path,
    status: 408,
  });
  error.isTimeout = true;
  return error;
}


export function createHttpClient({
  baseUrl,
  fetchImpl,
  requestTimeoutMs = 10000,
} = {}) {
  // In renderer-like environments (jsdom/electron), `window.fetch` is the expected override point.
  // Node 18+ provides a native `globalThis.fetch`; prefer `window.fetch` when present so tests can stub safely.
  const resolvedFetch = fetchImpl ?? globalThis.window?.fetch ?? globalThis.fetch;

  if (typeof resolvedFetch !== "function") {
    throw new Error("Fetch API 不可用，无法初始化 HTTP 客户端");
  }

  const inFlightJsonRequests = new Map();

  async function request(path, options = {}) {
    const {
      dedupeInFlight: _dedupeInFlight,
      dedupeKey: _dedupeKey,
      ...fetchOptions
    } = options;
    const method = String(fetchOptions.method ?? "GET").toUpperCase();
    const timeoutMs = Number(fetchOptions.timeoutMs ?? requestTimeoutMs);
    const controller = typeof AbortController === "function"
      ? new AbortController()
      : null;
    let timeoutId = null;
    let abortListener = null;
    let timeoutError = null;
    let didTimeout = false;

    if (controller && fetchOptions.signal) {
      if (fetchOptions.signal.aborted) {
        controller.abort();
      } else if (typeof fetchOptions.signal.addEventListener === "function") {
        abortListener = () => controller.abort();
        fetchOptions.signal.addEventListener("abort", abortListener, { once: true });
      }
    }

    const fetchPromise = resolvedFetch(buildUrl(baseUrl, path), {
      method,
      headers: {
        Accept: "application/json",
        ...fetchOptions.headers,
      },
      ...fetchOptions,
      signal: controller?.signal ?? fetchOptions.signal,
    });

    let response;
    try {
      response = await (
        Number.isFinite(timeoutMs) && timeoutMs > 0
          ? Promise.race([
            fetchPromise,
            new Promise((_, reject) => {
              timeoutId = globalThis.setTimeout(() => {
                timeoutError = buildTimeoutError({
                  method,
                  path,
                  timeoutMs,
                });
                didTimeout = true;
                controller?.abort();
                reject(timeoutError);
              }, timeoutMs);
            }),
          ])
          : fetchPromise
      );
    } catch (error) {
      if (didTimeout && timeoutError) {
        throw timeoutError;
      }
      throw error;
    } finally {
      if (timeoutId !== null) {
        globalThis.clearTimeout(timeoutId);
      }
      if (abortListener && typeof fetchOptions.signal?.removeEventListener === "function") {
        fetchOptions.signal.removeEventListener("abort", abortListener);
      }
    }

    if (!response.ok) {
      const message = typeof response.text === "function"
        ? await response.text()
        : `HTTP ${response.status}`;
      throw buildHttpError({
        message: message || `HTTP ${response.status}`,
        method,
        path,
        status: response.status,
      });
    }

    return response;
  }

  return {
    async getJson(path, options = {}) {
      const { dedupeInFlight = false, dedupeKey = null, ...requestOptions } = options;
      const method = String(requestOptions.method ?? "GET").toUpperCase();
      const shouldDedupe = dedupeInFlight && method === "GET";
      const inFlightKey = shouldDedupe
        ? String(dedupeKey || `${method} ${path}`)
        : null;

      if (inFlightKey && inFlightJsonRequests.has(inFlightKey)) {
        return inFlightJsonRequests.get(inFlightKey);
      }

      const nextPromise = request(path, requestOptions)
        .then((response) => response.json())
        .finally(() => {
          if (inFlightKey && inFlightJsonRequests.get(inFlightKey) === nextPromise) {
            inFlightJsonRequests.delete(inFlightKey);
          }
        });

      if (inFlightKey) {
        inFlightJsonRequests.set(inFlightKey, nextPromise);
      }

      return nextPromise;
    },
    async postJson(path, payload, options = {}) {
      const response = await request(path, {
        ...options,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        body: JSON.stringify(payload),
      });
      return response.json();
    },
    async patchJson(path, payload, options = {}) {
      const response = await request(path, {
        ...options,
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        body: JSON.stringify(payload),
      });
      return response.json();
    },
    async putJson(path, payload, options = {}) {
      const response = await request(path, {
        ...options,
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        body: JSON.stringify(payload),
      });
      return response.json();
    },
    async delete(path, options = {}) {
      await request(path, {
        ...options,
        method: "DELETE",
      });
    },
  };
}
