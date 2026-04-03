const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");

const { app, BrowserWindow, ipcMain } = require("electron");
const {
  DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  resolveDesktopRuntimeMode,
} = require("./electron_runtime_mode.cjs");
const { appendRendererDiagnostic } = require("./renderer_diagnostics_logger.cjs");


const projectRoot = path.resolve(__dirname, "..");
const rendererEntryPath = path.join(__dirname, "dist", "index.html");
const dbPath = path.join(projectRoot, "data", "app.db");
const desktopAppDisplayName = "C5 账号中心";
const desktopAppDirectoryName = "C5AccountCenter";
const desktopAppUserModelId = "com.c5.account-center";
const sessionMigrationMarkerName = ".c5-session-migrated";
const migratableSessionEntryNames = new Set([
  "Cookies",
  "Cookies-journal",
  "Cookies-shm",
  "Cookies-wal",
  "IndexedDB",
  "Local Storage",
  "Network Persistent State",
  "Session Storage",
  "SharedStorage",
  "Trust Tokens",
  "Trust Tokens-journal",
  "Trust Tokens-shm",
  "Trust Tokens-wal",
  "WebStorage",
  "blob_storage",
  "databases",
]);
const migratableNetworkSessionEntryNames = new Set([
  "Cookies",
  "Cookies-journal",
  "Cookies-shm",
  "Cookies-wal",
  "Network Persistent State",
  "NetworkDataMigrated",
  "Trust Tokens",
  "Trust Tokens-journal",
  "Trust Tokens-shm",
  "Trust Tokens-wal",
]);
let mainWindow = null;
let backend = null;
let bootstrapConfig = {
  ...DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  backendStatus: "starting",
};
let backendDependenciesPromise = null;
let windowStateDependenciesPromise = null;
let loadWindowState = null;
let saveWindowState = null;
let resolvePythonExecutable = null;
let startPythonBackend = null;


function readAppPath(appApi, targetPathName) {
  if (!appApi || typeof appApi.getPath !== "function") {
    return "";
  }

  try {
    const targetPath = appApi.getPath(targetPathName);
    return typeof targetPath === "string" ? targetPath : "";
  } catch {
    return "";
  }
}


function deriveLocalAppDataRoot(roamingRoot, pathApi = path) {
  if (!roamingRoot) {
    return "";
  }

  const normalizedRoamingRoot = typeof roamingRoot === "string" ? roamingRoot.trim() : "";
  if (!normalizedRoamingRoot) {
    return "";
  }

  const roamingParent = pathApi.dirname(normalizedRoamingRoot);
  const roamingLeafName = pathApi.basename(normalizedRoamingRoot).toLowerCase();

  if (!roamingParent || roamingParent === normalizedRoamingRoot) {
    return "";
  }

  if (roamingLeafName === "roaming") {
    return pathApi.join(roamingParent, "Local");
  }

  return roamingParent;
}


function isVolatileSessionEntry(entryName) {
  if (typeof entryName !== "string") {
    return false;
  }

  const normalizedEntryName = entryName.toLowerCase();
  return normalizedEntryName.includes("cache");
}


function isNetworkSessionEntry(entryName) {
  return typeof entryName === "string" && entryName.toLowerCase() === "network";
}


function shouldMigrateSessionEntry(entryName) {
  return migratableSessionEntryNames.has(entryName);
}


function shouldMigrateNetworkSessionEntry(entryName) {
  return migratableNetworkSessionEntryNames.has(entryName);
}


function shouldResetTargetSessionEntry(entryName) {
  return (
    isVolatileSessionEntry(entryName)
    || isNetworkSessionEntry(entryName)
    || shouldMigrateSessionEntry(entryName)
  );
}


function resolveDesktopStoragePaths({
  appApi = app,
  env = process.env,
  existsSync = fs.existsSync,
  pathApi = path,
  platform = process.platform,
} = {}) {
  if (platform !== "win32") {
    return null;
  }

  const roamingRoot = typeof env.APPDATA === "string" && env.APPDATA.trim()
    ? env.APPDATA.trim()
    : readAppPath(appApi, "appData");
  const localRoot = typeof env.LOCALAPPDATA === "string" && env.LOCALAPPDATA.trim()
    ? env.LOCALAPPDATA.trim()
    : deriveLocalAppDataRoot(roamingRoot, pathApi);

  if (!roamingRoot || !localRoot) {
    return null;
  }

  const legacyUserDataPath = readAppPath(appApi, "userData");
  const legacySessionDataPath = readAppPath(appApi, "sessionData") || legacyUserDataPath;
  const dedicatedUserDataPath = pathApi.join(roamingRoot, desktopAppDirectoryName);
  const dedicatedSessionDataPath = pathApi.join(localRoot, desktopAppDirectoryName, "session-data");

  return {
    sessionData: dedicatedSessionDataPath,
    userData: legacyUserDataPath && existsSync(legacyUserDataPath)
      ? legacyUserDataPath
      : dedicatedUserDataPath,
  };
}


function migrateLegacyNetworkSessionData({
  cpSync = fs.cpSync,
  legacySessionDataPath,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  readdirSync = fs.readdirSync,
  targetSessionDataPath,
} = {}) {
  try {
    const legacyNetworkPath = pathApi.join(legacySessionDataPath, "Network");
    const targetNetworkPath = pathApi.join(targetSessionDataPath, "Network");

    mkdirSync(targetNetworkPath, { recursive: true });

    let migrationFailed = false;
    for (const entryName of readdirSync(legacyNetworkPath)) {
      if (!shouldMigrateNetworkSessionEntry(entryName)) {
        continue;
      }
      try {
        cpSync(
          pathApi.join(legacyNetworkPath, entryName),
          pathApi.join(targetNetworkPath, entryName),
          {
            errorOnExist: false,
            force: true,
            recursive: true,
          },
        );
      } catch (error) {
        migrationFailed = true;
        console.warn(`Failed to migrate desktop network session entry ${entryName}`, error);
      }
    }

    return !migrationFailed;
  } catch (error) {
    console.warn("Failed to prepare desktop network session migration", error);
    return false;
  }
}


function migrateLegacySessionData({
  cpSync = fs.cpSync,
  existsSync = fs.existsSync,
  legacySessionDataPath,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  readdirSync = fs.readdirSync,
  rmSync = fs.rmSync,
  targetSessionDataPath,
  writeFileSync = fs.writeFileSync,
} = {}) {
  try {
    if (
      !legacySessionDataPath
      || !targetSessionDataPath
      || legacySessionDataPath === targetSessionDataPath
      || !existsSync(legacySessionDataPath)
    ) {
      return true;
    }

    mkdirSync(targetSessionDataPath, { recursive: true });
    const migrationMarkerPath = pathApi.join(targetSessionDataPath, sessionMigrationMarkerName);

    if (existsSync(migrationMarkerPath)) {
      return true;
    }

    if (typeof rmSync === "function") {
      for (const entryName of readdirSync(targetSessionDataPath)) {
        if (!shouldResetTargetSessionEntry(entryName)) {
          continue;
        }
        rmSync(pathApi.join(targetSessionDataPath, entryName), {
          force: true,
          recursive: true,
        });
      }
    }

    let migrationFailed = false;
    for (const entryName of readdirSync(legacySessionDataPath)) {
      if (isNetworkSessionEntry(entryName)) {
        const networkMigrationReady = migrateLegacyNetworkSessionData({
          cpSync,
          legacySessionDataPath,
          mkdirSync,
          pathApi,
          readdirSync,
          targetSessionDataPath,
        });

        migrationFailed = !networkMigrationReady || migrationFailed;
        continue;
      }

      if (!shouldMigrateSessionEntry(entryName)) {
        continue;
      }
      try {
        cpSync(
          pathApi.join(legacySessionDataPath, entryName),
          pathApi.join(targetSessionDataPath, entryName),
          {
            errorOnExist: false,
            force: true,
            recursive: true,
          },
        );
      } catch (error) {
        migrationFailed = true;
        console.warn(`Failed to migrate desktop session entry ${entryName}`, error);
      }
    }

    if (!migrationFailed && typeof writeFileSync === "function") {
      writeFileSync(migrationMarkerPath, "done", "utf8");
    }

    return !migrationFailed;
  } catch (error) {
    console.warn("Failed to migrate legacy desktop session data", error);
    return false;
  }
}


function configureDesktopStoragePaths({
  appApi = app,
  cpSync = fs.cpSync,
  env = process.env,
  existsSync = fs.existsSync,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  platform = process.platform,
  readdirSync = fs.readdirSync,
  writeFileSync = fs.writeFileSync,
} = {}) {
  const legacySessionDataPath = readAppPath(appApi, "sessionData") || readAppPath(appApi, "userData");
  const storagePaths = resolveDesktopStoragePaths({
    appApi,
    env,
    existsSync,
    pathApi,
    platform,
  });

  if (platform !== "win32") {
    return;
  }

  if (typeof appApi.setAppUserModelId === "function") {
    appApi.setAppUserModelId(desktopAppUserModelId);
  }

  if (typeof appApi.setName === "function") {
    appApi.setName(desktopAppDisplayName);
  }

  if (typeof appApi.setPath !== "function") {
    return;
  }

  if (!storagePaths) {
    return;
  }

  for (const [pathName, targetPath] of Object.entries(storagePaths)) {
    try {
      let configuredPath = targetPath;

      if (pathName === "sessionData") {
        const migrationReady = migrateLegacySessionData({
          cpSync,
          existsSync,
          legacySessionDataPath,
          mkdirSync,
          pathApi,
          readdirSync,
          writeFileSync,
          targetSessionDataPath: targetPath,
        });

        if (!migrationReady && legacySessionDataPath) {
          configuredPath = legacySessionDataPath;
        }
      }

      mkdirSync(configuredPath, { recursive: true });
      appApi.setPath(pathName, configuredPath);
    } catch (error) {
      console.warn(`Failed to configure desktop ${pathName} path`, error);
    }
  }
}


async function ensureWindowStateDependencies() {
  if (!windowStateDependenciesPromise) {
    windowStateDependenciesPromise = import("./window_state.js").then((windowStateModule) => {
      loadWindowState = windowStateModule.loadWindowState;
      saveWindowState = windowStateModule.saveWindowState;
    });
  }

  return windowStateDependenciesPromise;
}


async function ensureBackendDependencies() {
  if (!backendDependenciesPromise) {
    backendDependenciesPromise = import("./python_backend.js").then((pythonBackendModule) => {
      startPythonBackend = pythonBackendModule.startPythonBackend;
      resolvePythonExecutable = pythonBackendModule.resolvePythonExecutable;
    });
  }

  return backendDependenciesPromise;
}


function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }

        resolve(port);
      });
    });
    server.on("error", reject);
  });
}


function createWindow() {
  const windowState = loadWindowState();

  mainWindow = new BrowserWindow({
    ...windowState,
    show: false,
    title: "C5 账号中心",
    backgroundColor: "#111317",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "electron-preload.cjs"),
    },
  });

  mainWindow.on("close", () => {
    if (!mainWindow) {
      return;
    }

    saveWindowState(mainWindow.getBounds());
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  mainWindow.loadFile(rendererEntryPath);
}


function buildStartupFailureCopy(runtimeMode) {
  if (runtimeMode?.backendMode === "remote") {
    return "远程模式启动失败，请检查远程模式配置、服务状态或网络连通性。";
  }

  return "Python 后端未能成功拉起，请先确认 .venv 与 data/app.db 是否存在。";
}


function createFailureWindow(error, runtimeMode) {
  const message = encodeURIComponent(String(error instanceof Error ? error.message : error));
  const copy = encodeURIComponent(buildStartupFailureCopy(runtimeMode));
  const html = `data:text/html;charset=utf-8,<!doctype html><html lang="zh-CN"><body style="margin:0;font-family:'Microsoft YaHei UI',sans-serif;background:#111317;color:#f3efe6;display:grid;place-items:center;height:100vh"><main style="max-width:680px;padding:32px;border:1px solid rgba(255,255,255,.1);border-radius:20px;background:rgba(255,255,255,.04)"><h1 style="margin-top:0">账号中心桌面端启动失败</h1><p>${copy}</p><pre style="white-space:pre-wrap;color:#ffb0b0">${message}</pre></main></body></html>`;
  const failureWindow = new BrowserWindow({
    width: 880,
    height: 620,
    backgroundColor: "#111317",
  });
  failureWindow.loadURL(html);
}


async function bootstrapApplication({
  runtimeMode = resolveDesktopRuntimeMode(process.env),
  createFailureWindowImpl = createFailureWindow,
  createWindowImpl = createWindow,
  ensureBackendDependenciesImpl = ensureBackendDependencies,
  ensureWindowStateDependenciesImpl = ensureWindowStateDependencies,
  findAvailablePortImpl = findAvailablePort,
  resolvePythonExecutableImpl = null,
  startPythonBackendImpl = null,
} = {}) {
  bootstrapConfig = {
    ...DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
    backendMode: runtimeMode.backendMode,
    apiBaseUrl: runtimeMode.apiBaseUrl,
    runtimeWebSocketUrl: runtimeMode.runtimeWebSocketUrl,
    backendStatus: "starting",
  };

  try {
    if (runtimeMode.configurationError) {
      throw new Error(runtimeMode.configurationError);
    }

    await ensureWindowStateDependenciesImpl();

    if (!runtimeMode.shouldStartEmbeddedBackend) {
      bootstrapConfig = {
        ...bootstrapConfig,
        backendStatus: "ready",
      };
      createWindowImpl();
      return;
    }

    await ensureBackendDependenciesImpl();
    const port = await findAvailablePortImpl();
    const selectedResolvePythonExecutable = resolvePythonExecutableImpl ?? resolvePythonExecutable;
    const selectedStartPythonBackend = startPythonBackendImpl ?? startPythonBackend;
    const pythonExecutable = selectedResolvePythonExecutable(projectRoot);
    backend = await selectedStartPythonBackend({
      dbPath,
      pollIntervalMs: 250,
      portProvider: () => port,
      projectRoot,
      pythonExecutable,
      timeoutMs: 15000,
    });
    bootstrapConfig = {
      ...bootstrapConfig,
      apiBaseUrl: backend.baseUrl,
      backendStatus: "ready",
    };
    createWindowImpl();
  } catch (error) {
    bootstrapConfig = {
      ...bootstrapConfig,
      backendStatus: "failed",
    };
    createFailureWindowImpl(error, runtimeMode);
  }
}


ipcMain.on("desktop:get-bootstrap-config", (event) => {
  event.returnValue = bootstrapConfig;
});

ipcMain.on("desktop:log-renderer-diagnostic", (_event, payload) => {
  try {
    appendRendererDiagnostic(payload, { appApi: app });
  } catch (error) {
    console.error("Failed to append renderer diagnostic", error);
  }
});

configureDesktopStoragePaths();
app.whenReady().then(bootstrapApplication);

app.on("window-all-closed", () => {
  backend?.stop();
  backend = null;

  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  backend?.stop();
  backend = null;
});

app.on("activate", async () => {
  await ensureWindowStateDependencies();

  if (!BrowserWindow.getAllWindows().length && bootstrapConfig.backendStatus === "ready") {
    createWindow();
  }
});

module.exports = {
  bootstrapApplication,
  buildStartupFailureCopy,
  configureDesktopStoragePaths,
  deriveLocalAppDataRoot,
  migrateLegacySessionData,
  resolveDesktopStoragePaths,
};
