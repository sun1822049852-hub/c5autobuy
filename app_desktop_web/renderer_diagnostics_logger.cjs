const fs = require("node:fs");
const path = require("node:path");


function truncateString(value, maxLength = 4000) {
  const normalized = String(value ?? "");
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength)}...(truncated)`;
}


function normalizeValue(value, depth = 0) {
  if (depth > 4) {
    return "[MaxDepthExceeded]";
  }
  if (value === null || value === undefined) {
    return value ?? null;
  }
  if (typeof value === "string") {
    return truncateString(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "bigint") {
    return String(value);
  }
  if (value instanceof Error) {
    return {
      name: truncateString(value.name || "Error", 160),
      message: truncateString(value.message || ""),
      stack: value.stack ? truncateString(value.stack, 16000) : null,
    };
  }
  if (Array.isArray(value)) {
    return value.slice(0, 32).map((item) => normalizeValue(item, depth + 1));
  }
  if (typeof value === "object") {
    const entries = Object.entries(value).slice(0, 48);
    return Object.fromEntries(entries.map(([key, entryValue]) => [
      String(key),
      normalizeValue(entryValue, depth + 1),
    ]));
  }
  return truncateString(value);
}


function normalizePayload(payload, now) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {
      timestamp: now(),
      type: "renderer-diagnostic",
      href: null,
      details: {
        value: normalizeValue(payload),
      },
    };
  }

  return {
    timestamp: typeof payload.timestamp === "string" && payload.timestamp
      ? payload.timestamp
      : now(),
    type: typeof payload.type === "string" && payload.type
      ? payload.type
      : "renderer-diagnostic",
    href: typeof payload.href === "string" ? payload.href : null,
    details: normalizeValue(payload.details ?? {}),
  };
}


function resolveRendererDiagnosticsLogPath(appApi) {
  if (!appApi || typeof appApi.getPath !== "function") {
    throw new Error("Electron app path resolver is unavailable");
  }
  return path.join(appApi.getPath("userData"), "renderer-diagnostics.jsonl");
}


function appendRendererDiagnostic(
  payload,
  {
    appApi,
    appendFileSync = fs.appendFileSync,
    mkdirSync = fs.mkdirSync,
    now = () => new Date().toISOString(),
  } = {},
) {
  const logPath = resolveRendererDiagnosticsLogPath(appApi);
  mkdirSync(path.dirname(logPath), { recursive: true });

  const record = normalizePayload(payload, now);
  appendFileSync(logPath, `${JSON.stringify(record)}\n`, "utf8");
  return logPath;
}


module.exports = {
  appendRendererDiagnostic,
  normalizePayload,
  resolveRendererDiagnosticsLogPath,
};
