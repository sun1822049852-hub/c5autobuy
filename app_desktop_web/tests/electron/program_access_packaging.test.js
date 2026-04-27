import fs from "node:fs";
import Module from "node:module";
import { createRequire } from "node:module";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const configModulePath = require.resolve("../../program_access_config.cjs");
const electronMainModulePath = require.resolve("../../electron-main.cjs");


async function drainMicrotasks(iterations = 6) {
  for (let index = 0; index < iterations; index += 1) {
    // Keep yielding so async bootstrap branches can progress without timers.
    await Promise.resolve();
  }
}


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
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/certs/control-plane-ca.pem",
      },
    });

    expect(config.controlPlaneBaseUrl).toBe("https://8.138.39.139");
    expect(config.controlPlaneCaCertPath).toBe("C:/certs/control-plane-ca.pem");
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
            controlPlaneBaseUrl: "https://8.138.39.139",
            controlPlaneCaCertPath: "control_plane_ca.pem",
          });
        },
      },
      moduleDir: "C:\\demo\\project\\app_desktop_web",
      pathApi: path.win32,
      resourcesPath: "C:\\Users\\tester\\AppData\\Local\\Programs\\electron\\resources",
    });

    expect(config.controlPlaneBaseUrl).toBe("https://8.138.39.139");
    expect(config.controlPlaneCaCertPath).toBe("C:\\demo\\project\\app_desktop_web\\build\\control_plane_ca.pem");
  });

  it("passes packaged program access config into the embedded backend startup path", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const ensureManagedPythonRuntimeImpl = vi.fn().mockResolvedValue({
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/python-runtime/3.11.9/python.exe",
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    const resolvePythonExecutableImpl = vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe");

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
      ensureManagedPythonRuntimeImpl,
      resolvePythonExecutableImpl,
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/control_plane_ca.pem",
      })),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl: vi.fn(),
    });

    expect(ensureManagedPythonRuntimeImpl).toHaveBeenCalledWith(expect.objectContaining({
      appPrivateDir: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter\\app-private",
      packagedPythonDepsPath: expect.stringContaining("python_deps"),
      projectRoot: expect.any(String),
    }));
    expect(resolvePythonExecutableImpl).not.toHaveBeenCalled();
    expect(startPythonBackendImpl).toHaveBeenCalledWith(expect.objectContaining({
      dbPath: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter\\data\\app.db",
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/python-runtime/3.11.9/python.exe",
      programAccessConfig: {
        appPrivateDir: "C:\\Users\\tester\\AppData\\Roaming\\C5AccountCenter\\app-private",
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/Users/tester/AppData/Roaming/C5AccountCenter/control_plane_ca.pem",
        probeRegistrationReadiness: true,
        stage: "packaged_release",
      },
    }));
  });

  it("loads the renderer shell immediately and pushes a ready bootstrap update after the packaged backend becomes ready", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const createWindowImpl = vi.fn();
    const publishBootstrapConfigImpl = vi.fn();
    let resolveBackendStartup;
    const ensureManagedPythonRuntimeImpl = vi.fn().mockResolvedValue({
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/python-runtime/3.11.9/python.exe",
    });
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
      ensureManagedPythonRuntimeImpl,
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/demo/project/app_desktop_web/build/control_plane_ca.pem",
      })),
      startPythonBackendImpl,
      publishBootstrapConfigImpl,
      createWindowImpl,
      createFailureWindowImpl: vi.fn(),
    });

    await drainMicrotasks();
    expect(createWindowImpl).toHaveBeenNthCalledWith(1, { mode: "app" });
    expect(ensureManagedPythonRuntimeImpl).toHaveBeenCalledOnce();
    expect(startPythonBackendImpl).toHaveBeenCalledOnce();

    resolveBackendStartup({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    await bootstrapPromise;

    expect(createWindowImpl).toHaveBeenCalledTimes(1);
    expect(publishBootstrapConfigImpl).toHaveBeenCalledWith(expect.objectContaining({
      apiBaseUrl: "http://127.0.0.1:8233",
      backendMode: "embedded",
      backendStatus: "ready",
    }));
  });

  it("starts embedded backend prewarm work before window-state dependencies resolve", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const createWindowImpl = vi.fn();
    const publishBootstrapConfigImpl = vi.fn();
    let resolveBackendStartup;
    let resolveWindowStateDeps;
    const ensureWindowStateDependenciesImpl = vi.fn(() => new Promise((resolve) => {
      resolveWindowStateDeps = resolve;
    }));
    const ensureManagedPythonRuntimeImpl = vi.fn().mockResolvedValue({
      pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/python-runtime/3.11.9/python.exe",
    });
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
      ensureWindowStateDependenciesImpl,
      ensureBackendDependenciesImpl: vi.fn().mockResolvedValue(),
      findAvailablePortImpl: vi.fn().mockResolvedValue(8233),
      ensureManagedPythonRuntimeImpl,
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/demo/project/app_desktop_web/build/control_plane_ca.pem",
      })),
      startPythonBackendImpl,
      publishBootstrapConfigImpl,
      createWindowImpl,
      createFailureWindowImpl: vi.fn(),
    });

    await drainMicrotasks();
    expect(startPythonBackendImpl).toHaveBeenCalledOnce();
    expect(createWindowImpl).not.toHaveBeenCalled();
    expect(publishBootstrapConfigImpl).not.toHaveBeenCalled();

    resolveWindowStateDeps();
    await drainMicrotasks();
    expect(createWindowImpl).toHaveBeenCalledWith({ mode: "app" });

    resolveBackendStartup({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    await bootstrapPromise;

    expect(publishBootstrapConfigImpl).toHaveBeenCalledWith(expect.objectContaining({
      backendStatus: "ready",
    }));
  });

  it("reuses one in-flight embedded backend startup promise across concurrent bootstraps", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    let resolveBackendStartup;
    const startPythonBackendImpl = vi.fn(() => new Promise((resolve) => {
      resolveBackendStartup = resolve;
    }));
    const sharedBootstrapArgs = {
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
      ensureManagedPythonRuntimeImpl: vi.fn().mockResolvedValue({
        pythonExecutable: "C:/Users/tester/AppData/Roaming/C5AccountCenter/python-runtime/3.11.9/python.exe",
      }),
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/demo/project/app_desktop_web/build/control_plane_ca.pem",
      })),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl: vi.fn(),
      publishBootstrapConfigImpl: vi.fn(),
    };

    const firstBootstrapPromise = bootstrapApplication(sharedBootstrapArgs);
    await drainMicrotasks();
    const secondBootstrapPromise = bootstrapApplication(sharedBootstrapArgs);
    await drainMicrotasks();

    expect(startPythonBackendImpl).toHaveBeenCalledOnce();

    resolveBackendStartup({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    await Promise.all([firstBootstrapPromise, secondBootstrapPromise]);
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

  it("fails closed for packaged embedded startup when the control-plane base url is not https", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    const createFailureWindowImpl = vi.fn((error) => {
      expect(String(error)).toContain("https control plane base url");
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
        controlPlaneCaCertPath: "C:/demo/project/app_desktop_web/build/control_plane_ca.pem",
      })),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl,
    });

    expect(startPythonBackendImpl).not.toHaveBeenCalled();
    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
  });

  it("fails closed for packaged embedded startup when the control-plane CA cert path is missing", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    const createFailureWindowImpl = vi.fn((error) => {
      expect(String(error)).toContain("control plane CA cert path");
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
        controlPlaneBaseUrl: "https://8.138.39.139",
      })),
      startPythonBackendImpl,
      createWindowImpl: vi.fn(),
      createFailureWindowImpl,
    });

    expect(startPythonBackendImpl).not.toHaveBeenCalled();
    expect(createFailureWindowImpl).toHaveBeenCalledOnce();
  });

  it("fails closed before backend startup when packaged python runtime bootstrap fails", async () => {
    const electronHarness = createElectronHarness();
    const { bootstrapApplication } = loadElectronMainWithMocks({
      electron: electronHarness.electron,
    });
    const startPythonBackendImpl = vi.fn().mockResolvedValue({
      baseUrl: "http://127.0.0.1:8233",
      stop: vi.fn(),
    });
    const createFailureWindowImpl = vi.fn((error) => {
      expect(String(error)).toContain("download failed");
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
      ensureManagedPythonRuntimeImpl: vi.fn().mockRejectedValue(new Error("download failed")),
      resolvePythonExecutableImpl: vi.fn(() => "C:/demo/project/.venv/Scripts/python.exe"),
      readProgramAccessConfigImpl: vi.fn(() => ({
        controlPlaneBaseUrl: "https://8.138.39.139",
        controlPlaneCaCertPath: "C:/demo/project/app_desktop_web/build/control_plane_ca.pem",
      })),
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
      expect.objectContaining({ to: "python_deps" }),
      expect.objectContaining({ to: "test.wasm" }),
      expect.objectContaining({ to: "xsign.py" }),
    ]));
    expect(builderConfig.extraResources).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ to: ".venv" }),
    ]));
    expect(builderConfig.files).toEqual(expect.arrayContaining([
      "python_runtime_bootstrap.js",
      "python_runtime_config.cjs",
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
    expect(JSON.parse(fs.readFileSync(releaseConfigPath, "utf8"))).toEqual(expect.objectContaining({
      controlPlaneBaseUrl: expect.stringMatching(/^https:\/\//),
      controlPlaneCaCertPath: "control_plane_ca.pem",
    }));
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

  it("does not expose legacy bundled-runtime preflight helpers after switching to python_deps packaging", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const preflight = require(preflightModulePath);

    expect(preflight).not.toHaveProperty("resolveBundledPythonExecutable");
    expect(preflight).not.toHaveProperty("verifyEmbeddedPythonRuntime");
  });

  it("runs renderer build checks before verifying embedded python during packaging preflight", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");
    const ensureRendererBuildImpl = vi.fn();
    const preparePackagedPythonResourcesImpl = vi.fn(() => ({
      pythonDepsPath: "C:/demo/repo/app_desktop_web/build/python_deps",
      workspaceRoot: "C:/demo/repo",
    }));
    const verifyPackagedPythonResourcesImpl = vi.fn(() => ({
      dependencyRoot: "C:/demo/repo/app_desktop_web/build/python_deps",
      workspaceRoot: "C:/demo/repo",
    }));

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const { ensurePackagingPrerequisites } = require(preflightModulePath);

    const result = ensurePackagingPrerequisites({
      appDir: process.cwd(),
      ensureRendererBuildImpl,
      preparePackagedPythonResourcesImpl,
      verifyPackagedPythonResourcesImpl,
    });

    expect(ensureRendererBuildImpl).toHaveBeenCalledWith(process.cwd());
    expect(preparePackagedPythonResourcesImpl).toHaveBeenCalledWith({
      appDir: process.cwd(),
    });
    expect(verifyPackagedPythonResourcesImpl).toHaveBeenCalledWith({
      appDir: process.cwd(),
      preparedResources: {
        pythonDepsPath: "C:/demo/repo/app_desktop_web/build/python_deps",
        workspaceRoot: "C:/demo/repo",
      },
    });
    expect(result).toEqual({
      dependencyRoot: "C:/demo/repo/app_desktop_web/build/python_deps",
      workspaceRoot: "C:/demo/repo",
    });
  });

  it("surfaces python stderr when the packaged python resource preflight fails", () => {
    const preflightModulePath = path.join(process.cwd(), "electron-builder-preflight.cjs");
    const workspaceRoot = path.join("C:", "demo", "repo");
    const appDir = path.join(workspaceRoot, "app_desktop_web");
    const pythonDepsPath = path.join(appDir, "build", "python_deps");
    const outputSitePackagesPath = path.join(
      pythonDepsPath,
      "Lib",
      "site-packages",
    );
    const workspacePython = path.join(workspaceRoot, ".venv", "Scripts", "python.exe");

    expect(fs.existsSync(preflightModulePath)).toBe(true);
    const { verifyPackagedPythonResources } = require(preflightModulePath);

    expect(() => verifyPackagedPythonResources({
      appDir,
      existsSync(targetPath) {
        return targetPath === outputSitePackagesPath;
      },
      preparedResources: {
        outputSitePackagesPath,
        pythonDepsPath,
        pythonExecutable: workspacePython,
        workspaceRoot,
      },
      spawnSync: () => ({
        status: 1,
        stdout: "",
        stderr: "ModuleNotFoundError: No module named 'cryptography'",
      }),
    })).toThrow(/cryptography/);
  });
});
