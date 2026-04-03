const DEFAULT_DESKTOP_BOOTSTRAP_CONFIG = Object.freeze({
  backendMode: "embedded",
  apiBaseUrl: "http://127.0.0.1:8000",
  runtimeWebSocketUrl: "",
  backendStatus: "starting",
});


function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}


function resolveBackendMode(value) {
  const normalizedValue = normalizeText(value).toLowerCase();

  if (!normalizedValue) {
    return {
      backendMode: "embedded",
      configurationError: "",
    };
  }

  if (normalizedValue === "embedded" || normalizedValue === "remote") {
    return {
      backendMode: normalizedValue,
      configurationError: "",
    };
  }

  return {
    backendMode: "embedded",
    configurationError: 'DESKTOP_BACKEND_MODE must be either "embedded" or "remote" when provided.',
  };
}


function resolveDesktopRuntimeMode(source = {}) {
  const rawBackendMode = source.DESKTOP_BACKEND_MODE ?? source.backendMode;
  const { backendMode, configurationError: backendModeConfigurationError } = resolveBackendMode(rawBackendMode);
  const configuredApiBaseUrl = normalizeText(source.DESKTOP_API_BASE_URL || source.apiBaseUrl);
  const runtimeWebSocketUrl = normalizeText(
    source.DESKTOP_RUNTIME_WEBSOCKET_URL || source.runtimeWebSocketUrl,
  );
  const configurationError = backendModeConfigurationError || (
    backendMode === "remote" && !configuredApiBaseUrl
      ? "DESKTOP_API_BASE_URL is required when DESKTOP_BACKEND_MODE=remote."
      : ""
  );
  const apiBaseUrl = backendMode === "remote"
    ? configuredApiBaseUrl
    : (configuredApiBaseUrl || DEFAULT_DESKTOP_BOOTSTRAP_CONFIG.apiBaseUrl);

  return {
    backendMode,
    apiBaseUrl,
    configurationError,
    runtimeWebSocketUrl,
    shouldStartEmbeddedBackend: !configurationError && backendMode !== "remote",
  };
}


module.exports = {
  DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  resolveDesktopRuntimeMode,
};
