function normalizeBaseUrl(baseUrl = "") {
  return String(baseUrl).replace(/\/+$/, "");
}


function buildUrl(baseUrl, path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizeBaseUrl(baseUrl)}${normalizedPath}`;
}


export function createHttpClient({ baseUrl, fetchImpl } = {}) {
  const resolvedFetch = fetchImpl ?? globalThis.fetch;

  if (typeof resolvedFetch !== "function") {
    throw new Error("Fetch API 不可用，无法初始化 HTTP 客户端");
  }

  async function request(path, options = {}) {
    const response = await resolvedFetch(buildUrl(baseUrl, path), {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const message = typeof response.text === "function"
        ? await response.text()
        : `HTTP ${response.status}`;
      throw new Error(message || `HTTP ${response.status}`);
    }

    return response;
  }

  return {
    async getJson(path, options = {}) {
      const response = await request(path, options);
      return response.json();
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
    async delete(path, options = {}) {
      await request(path, {
        ...options,
        method: "DELETE",
      });
    },
  };
}
