import { createUiStateStore } from "../account-center/state/ui_state_store.js";


const DEFAULT_ACTIVE_ITEM = "account-center";
const VALID_ACTIVE_ITEMS = new Set([
  DEFAULT_ACTIVE_ITEM,
  "query-system",
  "purchase-system",
  "query-stats",
  "account-capability-stats",
  "diagnostics",
]);
const ACTIVE_ITEM_LABELS = {
  "account-center": "账号中心",
  "query-system": "配置管理",
  "purchase-system": "扫货系统",
  "query-stats": "查询统计",
  "account-capability-stats": "账号能力统计",
  diagnostics: "通用诊断",
};
const APP_SHELL_STORE = createUiStateStore("app-shell-state");
const QUERY_SYSTEM_VIEW_STORE = createUiStateStore("query-system-view-state");
const RENDERER_DIAGNOSTICS_STORE = createUiStateStore("renderer-diagnostics");
const RENDERER_SESSION_KEY = "desktop-web-renderer-session";


function resolveSessionStorage() {
  try {
    return globalThis.window?.sessionStorage ?? null;
  } catch {
    return null;
  }
}


function normalizeActiveItem(value) {
  const normalized = String(value || "");
  return VALID_ACTIVE_ITEMS.has(normalized) ? normalized : DEFAULT_ACTIVE_ITEM;
}


function normalizeSelectedConfigId(value) {
  if (!value) {
    return null;
  }
  return String(value);
}


function buildSessionMarker() {
  return `renderer-${Date.now()}`;
}


export function readAppShellState() {
  const state = APP_SHELL_STORE.read({ activeItem: DEFAULT_ACTIVE_ITEM });
  return {
    activeItem: normalizeActiveItem(state?.activeItem),
  };
}


export function writeAppShellState({ activeItem }) {
  APP_SHELL_STORE.write({
    activeItem: normalizeActiveItem(activeItem),
  });
}


export function readQuerySystemViewState() {
  const state = QUERY_SYSTEM_VIEW_STORE.read({ selectedConfigId: null });
  return {
    selectedConfigId: normalizeSelectedConfigId(state?.selectedConfigId),
  };
}


export function writeQuerySystemViewState({ selectedConfigId }) {
  QUERY_SYSTEM_VIEW_STORE.write({
    selectedConfigId: normalizeSelectedConfigId(selectedConfigId),
  });
}


export function initializeRendererReloadNotice({ activeItem }) {
  const windowObject = globalThis.window;
  if (!windowObject || windowObject.__APP_RENDERER_BOOTSTRAPPED__) {
    return null;
  }

  const normalizedActiveItem = normalizeActiveItem(activeItem);
  const sessionStorage = resolveSessionStorage();
  const sessionMarker = sessionStorage?.getItem(RENDERER_SESSION_KEY);
  const timestamp = new Date().toISOString();
  const diagnostics = RENDERER_DIAGNOSTICS_STORE.read({});

  let notice = null;
  if (sessionMarker) {
    const reloadCount = Math.max(0, Math.trunc(Number(diagnostics?.reloadCount ?? 0))) + 1;
    notice = {
      activeItem: normalizedActiveItem,
      activeItemLabel: ACTIVE_ITEM_LABELS[normalizedActiveItem] || normalizedActiveItem,
      detectedAt: timestamp,
      reloadCount,
    };
    RENDERER_DIAGNOSTICS_STORE.write({
      ...diagnostics,
      lastActiveItem: normalizedActiveItem,
      lastBootAt: timestamp,
      lastReloadAt: timestamp,
      lastSessionMarker: sessionMarker,
      reloadCount,
    });
  } else {
    sessionStorage?.setItem(RENDERER_SESSION_KEY, buildSessionMarker());
    RENDERER_DIAGNOSTICS_STORE.write({
      ...diagnostics,
      lastActiveItem: normalizedActiveItem,
      lastBootAt: timestamp,
    });
  }

  windowObject.__APP_RENDERER_BOOTSTRAPPED__ = true;
  return notice;
}


export function updateRendererActiveItem(activeItem) {
  const normalizedActiveItem = normalizeActiveItem(activeItem);
  const diagnostics = RENDERER_DIAGNOSTICS_STORE.read({});
  RENDERER_DIAGNOSTICS_STORE.write({
    ...diagnostics,
    lastActiveItem: normalizedActiveItem,
    lastUpdatedAt: new Date().toISOString(),
  });
}


export function resetAppShellRuntimeForTests() {
  if (!globalThis.window) {
    return;
  }
  delete globalThis.window.__APP_RENDERER_BOOTSTRAPPED__;
}
