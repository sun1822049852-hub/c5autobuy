import Module from "node:module";
import { createRequire } from "node:module";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  resolveDesktopRuntimeMode,
} from "../../electron_runtime_mode.cjs";

const require = createRequire(import.meta.url);
const electronMainModulePath = require.resolve("../../electron-main.cjs");

function createElectronHarness() {
  const app = {
    on: vi.fn(),
    quit: vi.fn(),
    whenReady: vi.fn(() => ({
      then: vi.fn(),
    })),
  };
  const ipcMain = {
    on: vi.fn(),
  };
  class BrowserWindow {}
  BrowserWindow.getAllWindows = vi.fn(() => []);

  return {
    electron: {
      BrowserWindow,
      app,
      ipcMain,
    },
  };
}

function loadElectronMainWithMocks({ electron } = {}) {
  delete require.cache[electronMainModulePath];
  const originalLoad = Module._load;

  Module._load = function mockedLoad(request, parent, isMain) {
    if (request === "electron") {
      return electron;
    }

    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    return require(electronMainModulePath);
  } finally {
    Module._load = originalLoad;
  }
}

afterEach(() => {
  delete require.cache[electronMainModulePath];
  vi.restoreAllMocks();
});


describe("electron remote runtime mode", () => {
  it("defaults to embedded backend mode with local bootstrap values", () => {
    const mode = resolveDesktopRuntimeMode({});

    expect(mode).toEqual({
      backendMode: "embedded",
      apiBaseUrl: DEFAULT_DESKTOP_BOOTSTRAP_CONFIG.apiBaseUrl,
      configurationError: "",
      runtimeWebSocketUrl: "",
      shouldStartEmbeddedBackend: true,
    });
  });

  it("switches to remote mode and skips embedded backend startup", () => {
    const mode = resolveDesktopRuntimeMode({
      DESKTOP_API_BASE_URL: "https://api.example.com",
      DESKTOP_BACKEND_MODE: "remote",
      DESKTOP_RUNTIME_WEBSOCKET_URL: "wss://api.example.com/ws/runtime",
    });

    expect(mode).toEqual({
      backendMode: "remote",
      apiBaseUrl: "https://api.example.com",
      configurationError: "",
      runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
      shouldStartEmbeddedBackend: false,
    });
  });

  it("flags remote mode without an api base url as a configuration failure", () => {
    const mode = resolveDesktopRuntimeMode({
      DESKTOP_BACKEND_MODE: "remote",
      DESKTOP_API_BASE_URL: "   ",
    });

    expect(mode).toEqual({
      backendMode: "remote",
      apiBaseUrl: "",
      configurationError: "DESKTOP_API_BASE_URL is required when DESKTOP_BACKEND_MODE=remote.",
      runtimeWebSocketUrl: "",
      shouldStartEmbeddedBackend: false,
    });
  });

  it("flags an explicit invalid backend mode as a configuration failure", () => {
    const mode = resolveDesktopRuntimeMode({
      DESKTOP_BACKEND_MODE: "remtoe",
    });

    expect(mode).toEqual({
      backendMode: "embedded",
      apiBaseUrl: DEFAULT_DESKTOP_BOOTSTRAP_CONFIG.apiBaseUrl,
      configurationError: 'DESKTOP_BACKEND_MODE must be either "embedded" or "remote" when provided.',
      runtimeWebSocketUrl: "",
      shouldStartEmbeddedBackend: false,
    });
  });

  it("skips embedded backend startup inside the main-process bootstrap path", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks(electronHarness);
    const ensureWindowStateDependenciesImpl = vi.fn().mockResolvedValue();
    const ensureBackendDependenciesImpl = vi.fn().mockResolvedValue();
    const startPythonBackendImpl = vi.fn();
    const createWindowImpl = vi.fn();
    const createFailureWindowImpl = vi.fn();

    await bootstrapApplication({
      runtimeMode: {
        backendMode: "remote",
        apiBaseUrl: "https://api.example.com",
        runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
        shouldStartEmbeddedBackend: false,
      },
      ensureWindowStateDependenciesImpl,
      ensureBackendDependenciesImpl,
      startPythonBackendImpl,
      createFailureWindowImpl,
      createWindowImpl,
    });

    expect(ensureWindowStateDependenciesImpl).toHaveBeenCalledOnce();
    expect(ensureBackendDependenciesImpl).not.toHaveBeenCalled();
    expect(startPythonBackendImpl).not.toHaveBeenCalled();
    expect(createWindowImpl).toHaveBeenCalledOnce();
    expect(createFailureWindowImpl).not.toHaveBeenCalled();
  });

  it("returns the remote bootstrap snapshot through desktop:get-bootstrap-config", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks(electronHarness);
    const bootstrapHandler = electronHarness.electron.ipcMain.on.mock.calls.find(
      ([channel]) => channel === "desktop:get-bootstrap-config",
    )?.[1];

    expect(typeof bootstrapHandler).toBe("function");

    await bootstrapApplication({
      runtimeMode: {
        backendMode: "remote",
        apiBaseUrl: "https://api.example.com",
        configurationError: "",
        runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
        shouldStartEmbeddedBackend: false,
      },
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      startPythonBackendImpl: vi.fn(),
      createFailureWindowImpl: vi.fn(),
      createWindowImpl: vi.fn(),
    });

    const event = {};
    bootstrapHandler(event);

    expect(event.returnValue).toEqual({
      backendMode: "remote",
      apiBaseUrl: "https://api.example.com",
      backendStatus: "ready",
      runtimeWebSocketUrl: "wss://api.example.com/ws/runtime",
    });
  });

  it("fails fast for remote mode when the api base url is missing", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks(electronHarness);
    const createWindowImpl = vi.fn();
    const createFailureWindowImpl = vi.fn();

    await bootstrapApplication({
      runtimeMode: resolveDesktopRuntimeMode({
        DESKTOP_BACKEND_MODE: "remote",
        DESKTOP_API_BASE_URL: " ",
      }),
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      startPythonBackendImpl: vi.fn(),
      createFailureWindowImpl,
      createWindowImpl,
    });

    expect(createWindowImpl).not.toHaveBeenCalled();
    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
    const [error, runtimeMode] = createFailureWindowImpl.mock.calls[0];
    expect(String(error)).toContain("DESKTOP_API_BASE_URL is required");
    expect(runtimeMode.backendMode).toBe("remote");
    expect(runtimeMode.apiBaseUrl).toBe("");
  });

  it("fails fast for an explicit invalid backend mode without starting embedded backend", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks(electronHarness);
    const ensureBackendDependenciesImpl = vi.fn().mockResolvedValue();
    const startPythonBackendImpl = vi.fn();
    const createWindowImpl = vi.fn();
    const createFailureWindowImpl = vi.fn();

    await bootstrapApplication({
      runtimeMode: resolveDesktopRuntimeMode({
        DESKTOP_BACKEND_MODE: "remtoe",
      }),
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl,
      startPythonBackendImpl,
      createFailureWindowImpl,
      createWindowImpl,
    });

    expect(ensureBackendDependenciesImpl).not.toHaveBeenCalled();
    expect(startPythonBackendImpl).not.toHaveBeenCalled();
    expect(createWindowImpl).not.toHaveBeenCalled();
    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
    const [error, runtimeMode] = createFailureWindowImpl.mock.calls[0];
    expect(String(error)).toContain("DESKTOP_BACKEND_MODE must be either");
    expect(runtimeMode.configurationError).toContain("DESKTOP_BACKEND_MODE must be either");
    expect(runtimeMode.shouldStartEmbeddedBackend).toBe(false);
  });

  it("uses remote failure copy without local embedded-backend troubleshooting hints", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication, buildStartupFailureCopy } = loadElectronMainWithMocks(electronHarness);
    const startupError = new Error("remote bootstrap failed");
    const createFailureWindowImpl = vi.fn((error, runtimeMode) => {
      expect(error).toBe(startupError);

      const copy = buildStartupFailureCopy(runtimeMode);
      expect(copy).toContain("远程模式");
      expect(copy).toContain("服务状态");
      expect(copy).not.toContain(".venv");
      expect(copy).not.toContain("data/app.db");
    });

    await bootstrapApplication({
      runtimeMode: {
        backendMode: "remote",
        apiBaseUrl: "https://api.example.com",
        configurationError: "",
        runtimeWebSocketUrl: "",
        shouldStartEmbeddedBackend: false,
      },
      ensureWindowStateDependenciesImpl: vi.fn().mockRejectedValue(startupError),
      createFailureWindowImpl,
    });

    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
  });
});
