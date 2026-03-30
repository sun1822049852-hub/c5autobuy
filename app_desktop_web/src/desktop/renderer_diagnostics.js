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
    return Object.fromEntries(Object.entries(value).slice(0, 48).map(([key, entryValue]) => [
      String(key),
      normalizeValue(entryValue, depth + 1),
    ]));
  }
  return truncateString(value);
}


function getDesktopApp() {
  return globalThis.window?.desktopApp ?? null;
}


export function logRendererDiagnostic(type, details = {}) {
  const desktopApp = getDesktopApp();
  if (!desktopApp || typeof desktopApp.logRendererDiagnostic !== "function") {
    return false;
  }

  desktopApp.logRendererDiagnostic({
    type: typeof type === "string" && type ? type : "renderer-diagnostic",
    timestamp: new Date().toISOString(),
    href: globalThis.window?.location?.href ?? null,
    details: normalizeValue(details),
  });
  return true;
}


export function buildWindowErrorDetails(event) {
  const error = event?.error;
  return {
    message: event?.message ? String(event.message) : (error?.message ? String(error.message) : "unknown error"),
    filename: event?.filename ? String(event.filename) : null,
    lineno: Number.isFinite(Number(event?.lineno)) ? Number(event.lineno) : null,
    colno: Number.isFinite(Number(event?.colno)) ? Number(event.colno) : null,
    error: normalizeValue(error),
  };
}


export function buildUnhandledRejectionDetails(event) {
  return {
    reason: normalizeValue(event?.reason),
  };
}
