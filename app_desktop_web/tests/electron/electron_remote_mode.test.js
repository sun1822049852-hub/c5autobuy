import Module from "node:module";
import { createRequire } from "node:module";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  resolveDesktopRuntimeMode,
} from "../../electron_runtime_mode.cjs";

const require = createRequire(import.meta.url);
const electronMainModulePath = require.resolve("../../electron-main.cjs");

function normalizePathSeparators(targetPath) {
  return String(targetPath).replaceAll("/", "\\");
}

function createElectronHarness() {
  const app = {
    on: vi.fn(),
    setAppUserModelId: vi.fn(),
    setName: vi.fn(),
    setPath: vi.fn(),
    getPath: vi.fn((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "cache") {
        return "C:\\Users\\tester\\AppData\\Local\\electron\\Cache";
      }
      return "";
    }),
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

function loadElectronMainWithMocks({
  electron,
  fsModule = {
    cpSync: vi.fn(),
    existsSync: vi.fn(() => false),
    mkdirSync: vi.fn(),
    readdirSync: vi.fn(() => []),
  },
  platform = "win32",
} = {}) {
  delete require.cache[electronMainModulePath];
  const originalLoad = Module._load;
  const originalPlatformDescriptor = Object.getOwnPropertyDescriptor(process, "platform");
  const canOverridePlatform = Boolean(
    typeof platform === "string"
    && originalPlatformDescriptor
    && originalPlatformDescriptor.configurable,
  );

  Module._load = function mockedLoad(request, parent, isMain) {
    if (request === "electron") {
      return electron;
    }
    if (request === "node:fs") {
      return fsModule;
    }

    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    if (canOverridePlatform) {
      Object.defineProperty(process, "platform", {
        configurable: true,
        value: platform,
      });
    }

    return require(electronMainModulePath);
  } finally {
    Module._load = originalLoad;
    if (canOverridePlatform && originalPlatformDescriptor) {
      Object.defineProperty(process, "platform", originalPlatformDescriptor);
    }
  }
}

afterEach(() => {
  delete require.cache[electronMainModulePath];
  vi.restoreAllMocks();
});


describe("electron remote runtime mode", () => {
  it("configures dedicated desktop storage paths before the app bootstraps", () => {
    const electronHarness = createElectronHarness();
    const mkdirSync = vi.fn();
    const originalAppData = process.env.APPDATA;
    const originalLocalAppData = process.env.LOCALAPPDATA;

    process.env.APPDATA = "C:\\Users\\tester\\AppData\\Roaming";
    process.env.LOCALAPPDATA = "C:\\Users\\tester\\AppData\\Local";

    try {
      loadElectronMainWithMocks({
        electron: electronHarness.electron,
        fsModule: {
          existsSync: vi.fn(() => false),
          mkdirSync,
        },
      });
    } finally {
      if (typeof originalAppData === "string") {
        process.env.APPDATA = originalAppData;
      } else {
        delete process.env.APPDATA;
      }

      if (typeof originalLocalAppData === "string") {
        process.env.LOCALAPPDATA = originalLocalAppData;
      } else {
        delete process.env.LOCALAPPDATA;
      }
    }

    expect(electronHarness.electron.app.setAppUserModelId).toHaveBeenCalledWith("com.c5.trading-assistant");
    expect(electronHarness.electron.app.setName).toHaveBeenCalledWith("C5 交易助手");
    expect(mkdirSync.mock.calls.map(([targetPath]) => normalizePathSeparators(targetPath))).toContain(
      "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter",
    );
    expect(mkdirSync.mock.calls.map(([targetPath]) => normalizePathSeparators(targetPath))).toContain(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
    );
    expect(
      electronHarness.electron.app.setPath.mock.calls.map(([targetName, targetPath]) => [
        targetName,
        normalizePathSeparators(targetPath),
      ]),
    ).toContainEqual([
      "userData",
      "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter",
    ]);
    expect(
      electronHarness.electron.app.setPath.mock.calls.map(([targetName, targetPath]) => [
        targetName,
        normalizePathSeparators(targetPath),
      ]),
    ).toContainEqual([
      "sessionData",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
    ]);
  });

  it("skips dedicated desktop storage path rewrites outside Windows", () => {
    const electronHarness = createElectronHarness();
    const mkdirSync = vi.fn();
    const { resolveDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        existsSync: vi.fn(() => false),
        mkdirSync,
      },
      platform: "linux",
    });

    const storagePaths = resolveDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      pathApi: path.win32,
      platform: "linux",
    });

    expect(storagePaths).toBeNull();
    expect(mkdirSync).not.toHaveBeenCalled();
    expect(electronHarness.electron.app.setPath).not.toHaveBeenCalled();
    expect(electronHarness.electron.app.setAppUserModelId).not.toHaveBeenCalled();
  });

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

  it("derives local app data from the roaming appData path when LOCALAPPDATA is unavailable", () => {
    const electronHarness = createElectronHarness();
    const { resolveDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });

    const storagePaths = resolveDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {},
      pathApi: path.win32,
      platform: "win32",
    });

    expect(storagePaths).toEqual({
      sessionData: "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
      userData: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter",
    });
  });

  it("keeps legacy user data but moves session data into the dedicated directory for upgraded installs", () => {
    const electronHarness = createElectronHarness();
    const legacyUserDataPath = "C:\\Users\\tester\\AppData\\Roaming\\electron";
    const { resolveDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        existsSync: vi.fn((targetPath) => targetPath === legacyUserDataPath),
        mkdirSync: vi.fn(),
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "cache") {
        return "C:\\Users\\tester\\AppData\\Local\\electron\\Cache";
      }
      if (target === "sessionData" || target === "userData") {
        return legacyUserDataPath;
      }
      return "";
    });

    const storagePaths = resolveDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync: (targetPath) => targetPath === legacyUserDataPath,
      pathApi: path.win32,
      platform: "win32",
    });

    expect(storagePaths).toEqual({
      sessionData: "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
      userData: legacyUserDataPath,
    });
  });

  it("retries copying legacy session entries into an existing dedicated session directory", () => {
    const electronHarness = createElectronHarness();
    const cpSync = vi.fn();
    const existsSync = vi.fn((targetPath) => (
      targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron"
      || targetPath === "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data"
    ));
    const mkdirSync = vi.fn();
    const rmSync = vi.fn();
    const readdirSync = vi.fn((targetPath) => {
      const normalizedPath = normalizePathSeparators(targetPath);
      if (normalizedPath.endsWith("\\session-data")) {
        return ["Cache", "GPUCache", "Local Storage", "Network", "keep-me"];
      }
      if (normalizedPath.endsWith("\\electron")) {
        return ["Cache", "Local Storage", "Network"];
      }
      if (normalizedPath.endsWith("\\electron\\Network")) {
        return [
          "Cookies",
          "Cookies-journal",
          "Cookies-shm",
          "Cookies-wal",
          "GPUCache",
          "Network Persistent State",
          "Trust Tokens",
          "Trust Tokens-journal",
          "Trust Tokens-shm",
          "Trust Tokens-wal",
        ];
      }
      return [];
    });
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        rmSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "cache") {
        return "C:\\Users\\tester\\AppData\\Local\\electron\\Cache";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    rmSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      rmSync,
    });

    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cache",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\GPUCache",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Local Storage",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).not.toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\keep-me",
      expect.anything(),
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Local Storage",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Local Storage",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).not.toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Cache",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cache",
      expect.anything(),
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Cookies",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Cookies",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Cookies-shm",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Cookies-shm",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Cookies-wal",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Cookies-wal",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Network Persistent State",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Network Persistent State",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).not.toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\GPUCache",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\GPUCache",
      expect.anything(),
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Trust Tokens",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Trust Tokens",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Trust Tokens-journal",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Trust Tokens-journal",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Trust Tokens-shm",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Trust Tokens-shm",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Network\\Trust Tokens-wal",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Network\\Trust Tokens-wal",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
    );
  });

  it("migrates root cookie sqlite sidecars and clears stale target copies during retry", () => {
    const electronHarness = createElectronHarness();
    const cpSync = vi.fn();
    const existsSync = vi.fn((targetPath) => (
      targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron"
      || targetPath === "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data"
    ));
    const mkdirSync = vi.fn();
    const rmSync = vi.fn();
    const readdirSync = vi.fn((targetPath) => {
      const normalizedPath = normalizePathSeparators(targetPath);
      if (normalizedPath.endsWith("\\session-data")) {
        return ["Cookies", "Cookies-shm", "Cookies-wal", "keep-me"];
      }
      if (normalizedPath.endsWith("\\electron")) {
        return ["Cookies", "Cookies-shm", "Cookies-wal"];
      }
      return [];
    });
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        rmSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    rmSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      rmSync,
    });

    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies-shm",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies-wal",
      {
        force: true,
        recursive: true,
      },
    );
    expect(rmSync).not.toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\keep-me",
      expect.anything(),
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Cookies",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Cookies-shm",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies-shm",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Cookies-wal",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies-wal",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
    );
  });

  it("skips legacy session migration once the dedicated migration marker exists", () => {
    const electronHarness = createElectronHarness();
    const cpSync = vi.fn();
    const existsSync = vi.fn((targetPath) => (
      targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron"
      || targetPath === "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\.c5-session-migrated"
    ));
    const mkdirSync = vi.fn();
    const readdirSync = vi.fn(() => ["Cookies"]);
    const writeFileSync = vi.fn();
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        writeFileSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    writeFileSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      writeFileSync,
    });

    expect(cpSync).not.toHaveBeenCalled();
    expect(writeFileSync).not.toHaveBeenCalled();
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
    );
  });

  it("keeps the legacy session path for the current launch when migration of a critical entry fails", () => {
    const electronHarness = createElectronHarness();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const cpSync = vi.fn((sourcePath) => {
      if (String(sourcePath).endsWith("\\Cookies")) {
        throw new Error("copy failed");
      }
    });
    const existsSync = vi.fn((targetPath) => targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron");
    const mkdirSync = vi.fn();
    const readdirSync = vi.fn(() => ["Cookies"]);
    const writeFileSync = vi.fn();
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        writeFileSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    writeFileSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      writeFileSync,
    });

    expect(writeFileSync).not.toHaveBeenCalled();
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Roaming\\electron",
    );
  });

  it("keeps the legacy session path when writing the migration marker fails", () => {
    const electronHarness = createElectronHarness();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const cpSync = vi.fn();
    const existsSync = vi.fn((targetPath) => targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron");
    const mkdirSync = vi.fn();
    const readdirSync = vi.fn(() => ["Cookies"]);
    const writeFileSync = vi.fn(() => {
      throw new Error("marker failed");
    });
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        writeFileSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    writeFileSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      writeFileSync,
    });

    expect(cpSync).toHaveBeenCalledWith(
      "C:\\Users\\tester\\AppData\\Roaming\\electron\\Cookies",
      "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data\\Cookies",
      {
        errorOnExist: false,
        force: true,
        recursive: true,
      },
    );
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Roaming\\electron",
    );
  });

  it("keeps the legacy session path when reading legacy network session entries fails", () => {
    const electronHarness = createElectronHarness();
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const cpSync = vi.fn();
    const existsSync = vi.fn((targetPath) => targetPath === "C:\\Users\\tester\\AppData\\Roaming\\electron");
    const mkdirSync = vi.fn();
    const readdirSync = vi.fn((targetPath) => {
      const normalizedPath = normalizePathSeparators(targetPath);
      if (normalizedPath.endsWith("\\electron")) {
        return ["Network"];
      }
      if (normalizedPath.endsWith("\\electron\\Network")) {
        throw new Error("read failed");
      }
      return [];
    });
    const writeFileSync = vi.fn();
    const { configureDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
      fsModule: {
        cpSync,
        existsSync,
        mkdirSync,
        readdirSync,
        writeFileSync,
      },
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      if (target === "sessionData" || target === "userData") {
        return "C:\\Users\\tester\\AppData\\Roaming\\electron";
      }
      return "";
    });

    cpSync.mockClear();
    mkdirSync.mockClear();
    writeFileSync.mockClear();
    electronHarness.electron.app.setPath.mockClear();

    configureDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      existsSync,
      mkdirSync,
      pathApi: path.win32,
      platform: "win32",
      readdirSync,
      writeFileSync,
    });

    expect(writeFileSync).not.toHaveBeenCalled();
    expect(electronHarness.electron.app.setPath).toHaveBeenCalledWith(
      "sessionData",
      "C:\\Users\\tester\\AppData\\Roaming\\electron",
    );
  });

  it("does not depend on cache path fallback when APPDATA and LOCALAPPDATA are already provided", () => {
    const electronHarness = createElectronHarness();
    const { resolveDesktopStoragePaths } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });

    electronHarness.electron.app.getPath.mockImplementation((target) => {
      if (target === "cache") {
        throw new Error("cache path should not be read when LOCALAPPDATA is available");
      }
      if (target === "userData" || target === "sessionData") {
        return "";
      }
      if (target === "appData") {
        return "C:\\Users\\tester\\AppData\\Roaming";
      }
      return "";
    });

    const storagePaths = resolveDesktopStoragePaths({
      appApi: electronHarness.electron.app,
      env: {
        APPDATA: "C:\\Users\\tester\\AppData\\Roaming",
        LOCALAPPDATA: "C:\\Users\\tester\\AppData\\Local",
      },
      pathApi: path.win32,
      platform: "win32",
    });

    expect(storagePaths).toEqual({
      sessionData: "C:\\Users\\tester\\AppData\\Local\\C5AccountCenter\\session-data",
      userData: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter",
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
