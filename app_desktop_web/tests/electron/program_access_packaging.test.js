import fs from "node:fs";
import Module from "node:module";
import { createRequire } from "node:module";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const configModulePath = require.resolve("../../program_access_config.cjs");
const electronMainModulePath = require.resolve("../../electron-main.cjs");


function createElectronHarness() {
  const app = {
    getPath: vi.fn(() => "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter"),
    isPackaged: true,
    on: vi.fn(),
    quit: vi.fn(),
    setAppUserModelId: vi.fn(),
    setName: vi.fn(),
    setPath: vi.fn(),
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
    appendFileSync: vi.fn(),
    existsSync: vi.fn(() => false),
    mkdirSync: vi.fn(),
    readdirSync: vi.fn(() => []),
  },
} = {}) {
  delete require.cache[electronMainModulePath];
  const originalLoad = Module._load;

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
    return require(electronMainModulePath);
  } finally {
    Module._load = originalLoad;
  }
}


describe("program access packaging config", () => {
  it("declares a packaging preflight for both unpacked and installer builds", () => {
    const packageJsonPath = path.join(process.cwd(), "package.json");
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

    expect(packageJson.scripts["prepack:win"]).toBe("node electron-builder-preflight.cjs");
    expect(packageJson.scripts["prebuild:win"]).toBe("node electron-builder-preflight.cjs");
  });

  it("reads the packaged control-plane base url from file config", () => {
    delete require.cache[configModulePath];
    const { readProgramAccessConfig } = require(configModulePath);

    const config = readProgramAccessConfig({
      fileConfig: {
        controlPlaneBaseUrl: "http://8.138.39.139:18787",
      },
    });

    expect(config.controlPlaneBaseUrl).toBe("http://8.138.39.139:18787");
  });

  it("reads the source control-plane base url from build/client_config.release.json when unpackaged", () => {
    delete require.cache[configModulePath];
    const { readProgramAccessConfig } = require(configModulePath);
    const sourceConfigPath = path.win32.join(
      "C:\\demo\\project\\app_desktop_web",
      "build",
      "client_config.release.json",
    );

    const config = readProgramAccessConfig({
      appApi: {
        getPath: () => "",
      },
      env: {},
      fsApi: {
        existsSync(targetPath) {
          return targetPath === sourceConfigPath;
        },
        readFileSync(targetPath) {
          if (targetPath !== sourceConfigPath) {
            throw new Error(`unexpected path read: ${targetPath}`);
          }
          return JSON.stringify({
            controlPlaneBaseUrl: "http://8.138.39.139:18787",
          });
        },
      },
      moduleDir: "C:\\demo\\project\\app_desktop_web",
      pathApi: path.win32,
      resourcesPath: "C:\\Users\\tester\\AppData\\Local\\Programs\\electron\\resources",
    });

    expect(config.controlPlaneBaseUrl).toBe("http://8.138.39.139:18787");
  });

  it("passes packaged program access config into the embedded backend startup path", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });

    await bootstrapApplication({
      runtimeMode: {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:8000",
        configurationError: "",
        runtimeWebSocketUrl: "",
        shouldStartEmbeddedBackend: true,
      },
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      findAvailablePortImpl: vi.fn().mockResolvedValue(8233),
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "http://8.138.39.139:18787",
      })),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl: vi.fn(),
    });

    expect(startPythonBackendImpl).toHaveBeenCalledWith(expect.objectContaining({
      dbPath: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter\\data\\app.db",
      programAccessConfig: {
        appPrivateDir: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter\\app-private",
        controlPlaneBaseUrl: "http://8.138.39.139:18787",
        stage: "packaged_release",
      },
    }));
  });

  it("shows a loading window before the packaged embedded backend becomes ready", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const createWindowImpl = vi.fn();
    let resolveBackendStartup;
    const startPythonBackendImpl = vi.fn(() => new Promise((resolve) => {
      resolveBackendStartup = resolve;
    }));

    const bootstrapPromise = bootstrapApplication({
      runtimeMode: {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:8000",
        configurationError: "",
        runtimeWebSocketUrl: "",
        shouldStartEmbeddedBackend: true,
      },
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      findAvailablePortImpl: vi.fn().mockResolvedValue(8233),
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "http://8.138.39.139:18787",
      })),
      startPythonBackendImpl,
      createWindowImpl,
      createFailureWindowImpl: vi.fn(),
    });

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(createWindowImpl).toHaveBeenNthCalledWith(1, { mode: "loading" });
    expect(startPythonBackendImpl).toHaveBeenCalledOnce();

    resolveBackendStartup({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    await bootstrapPromise;

    expect(createWindowImpl).toHaveBeenNthCalledWith(2, { mode: "app" });
  });

  it("fails closed for packaged embedded startup when the control-plane base url is missing", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication, buildStartupFailureCopy } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    const createFailureWindowImpl = vi.fn((error, runtimeMode) => {
      expect(String(error)).toContain("control plane base url");
      expect(buildStartupFailureCopy(runtimeMode, { isPackaged: true })).toBe("服务器连接失败，请稍后重试。");
    });

    await bootstrapApplication({
      runtimeMode: {
        backendMode: "embedded",
        apiBaseUrl: "http://127.0.0.1:8000",
        configurationError: "",
        runtimeWebSocketUrl: "",
        shouldStartEmbeddedBackend: true,
      },
      ensureWindowStateDependenciesImpl: vi.fn().mockResolvedValue(),
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      findAvailablePortImpl: vi.fn().mockResolvedValue(8233),
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({})),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl,
    });

    expect(startPythonBackendImpl).not.toHaveBeenCalled();
    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
  });

  it("ships electron-builder config and the release client config file", () => {
    const appRoot = path.resolve(process.cwd());
    const builderConfigPath = path.join(appRoot, "electron-builder.config.cjs");
    const builderPathsModulePath = path.join(appRoot, "electron-builder-paths.cjs");
    const releaseConfigPath = path.join(appRoot, "build", "client_config.release.json");

    expect(fs.existsSync(builderConfigPath)).toBe(true);
    expect(fs.existsSync(builderPathsModulePath)).toBe(true);
    const builderConfig = require(builderConfigPath);
    expect(Object.getOwnPropertyNames(builderConfig)).not.toContain("resolveBundledResourcePath");
    expect(Object.getOwnPropertyNames(builderConfig)).not.toContain("buildElectronBuilderConfig");
    expect(builderConfig.appId).toBe("com.c5.trading-assistant");
    expect(builderConfig.productName).toBe("C5 交易助手");
    expect(builderConfig.extraResources).toEqual(expect.arrayContaining([
      expect.objectContaining({ to: "client_config.release.json" }),
      expect.objectContaining({ to: "app_backend" }),
      expect.objectContaining({ to: "xsign.py" }),
      expect.objectContaining({ to: ".venv" }),
    ]));
    expect(builderConfig.win).toEqual(expect.objectContaining({
      signAndEditExecutable: false,
    }));
    expect(builderConfig.nsis).toEqual(expect.objectContaining({
      oneClick: false,
      allowToChangeInstallationDirectory: true,
      createDesktopShortcut: "always",
      createStartMenuShortcut: true,
      perMachine: false,
    }));
    expect(JSON.parse(fs.readFileSync(releaseConfigPath, "utf8")).controlPlaneBaseUrl).toMatch(/^http:\/\//);
  });

  it("ships an explicit local debug client config file that keeps control plane auth disabled", () => {
    const appRoot = path.resolve(process.cwd());
    const localDebugConfigPath = path.join(appRoot, "build", "client_config.local_debug.json");

    expect(fs.existsSync(localDebugConfigPath)).toBe(true);
    expect(JSON.parse(fs.readFileSync(localDebugConfigPath, "utf8"))).toEqual({
      controlPlaneBaseUrl: "",
    });
  });

  it("resolves the bundled python runtime from the repo root when app_desktop_web runs inside a worktree", () => {
    const builderPathsModulePath = path.join(process.cwd(), "electron-builder-paths.cjs");
    expect(fs.existsSync(builderPathsModulePath)).toBe(true);

    const { resolveBundledResourcePath } = require(builderPathsModulePath);
    const repoRoot = path.join("C:", "demo", "repo");
    const worktreeAppDir = path.join(repoRoot, ".worktrees", "program-control-plane-chunk1", "app_desktop_web");
    const repoVenv = path.join(repoRoot, ".venv");

    expect(resolveBundledResourcePath({
      appDir: worktreeAppDir,
      resourcePath: ".venv",
      existsSync(targetPath) {
        return targetPath === repoVenv;
      },
    })).toBe(repoVenv);
  });

  it("verifies the embedded python runtime can import app_backend.main before packaging", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");
    const repoRoot = path.join("C:", "demo", "repo");
    const workspaceRoot = path.join(repoRoot, ".worktrees", "program-control-plane-chunk1");
    const worktreeAppDir = path.join(workspaceRoot, "app_desktop_web");
    const repoVenvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
    const worktreeBackend = path.join(workspaceRoot, "app_backend");
    const spawnSync = vi.fn(() => ({
      status: 0,
      stdout: "",
      stderr: "",
    }));

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const { verifyEmbeddedPythonRuntime } = require(preflightModulePath);

    expect(() => verifyEmbeddedPythonRuntime({
      appDir: worktreeAppDir,
      existsSync(targetPath) {
        return targetPath === repoVenvPython || targetPath === worktreeBackend;
      },
      spawnSync,
    })).not.toThrow();

    expect(spawnSync).toHaveBeenCalledWith(
      repoVenvPython,
      [
        "-c",
        expect.stringContaining("from app_backend.main import main"),
      ],
      expect.objectContaining({
        cwd: workspaceRoot,
        encoding: "utf8",
        stdio: "pipe",
      }),
    );
  });

  it("runs renderer build checks before verifying embedded python during packaging preflight", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");
    const ensureRendererBuildImpl = vi.fn();
    const verifyEmbeddedPythonRuntimeImpl = vi.fn(() => ({
      pythonExecutable: "C:/demo/repo/.venv/Scripts/python.exe",
      workspaceRoot: "C:/demo/repo",
    }));

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const { ensurePackagingPrerequisites } = require(preflightModulePath);

    const result = ensurePackagingPrerequisites({
      appDir: process.cwd(),
      ensureRendererBuildImpl,
      verifyEmbeddedPythonRuntimeImpl,
    });

    expect(ensureRendererBuildImpl).toHaveBeenCalledWith(process.cwd());
    expect(verifyEmbeddedPythonRuntimeImpl).toHaveBeenCalledWith({
      appDir: process.cwd(),
    });
    expect(result).toEqual({
      pythonExecutable: "C:/demo/repo/.venv/Scripts/python.exe",
      workspaceRoot: "C:/demo/repo",
    });
  });

  it("surfaces python stderr when the embedded runtime preflight fails", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");
    const workspaceRoot = path.join("C:", "demo", "repo");
    const appDir = path.join(workspaceRoot, "app_desktop_web");
    const workspacePython = path.join(workspaceRoot, ".venv", "Scripts", "python.exe");

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const { verifyEmbeddedPythonRuntime } = require(preflightModulePath);

    expect(() => verifyEmbeddedPythonRuntime({
      appDir,
      existsSync(targetPath) {
        return targetPath === workspacePython || targetPath === path.join(workspaceRoot, "app_backend");
      },
      spawnSync: () => ({
        status: 1,
        stdout: "",
        stderr: "ModuleNotFoundError: No module named 'cryptography'",
      }),
    })).toThrow(/cryptography/);
  });
});
