const fs = require("node:fs");
const path = require("node:path");
const net = require("node:net");

const { app, BrowserWindow, ipcMain } = require("electron");
const {
  DEFAULT_DESKTOP_BOOTSTRAP_CONFIG,
  resolveDesktopRuntimeMode,
} = require("./electron_runtime_mode.cjs");
const { readProgramAccessConfig } = require("./program_access_config.cjs");
const { appendRendererDiagnostic } = require("./renderer_diagnostics_logger.cjs");


const projectRoot = path.resolve(__dirname, "..");
const rendererEntryPath = path.join(__dirname, "dist", "index.html");
const desktopAppDisplayName = "C5 交易助手";
const desktopAppDirectoryName = "C5AccountCenter";
const desktopAppUserModelId = "com.c5.trading-assistant";
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


function resolveEmbeddedBackendPaths({
  appApi = app,
  pathApi = path,
  packaged = appApi?.isPackaged === true,
  projectRootPath = projectRoot,
} = {}) {
  if (!packaged) {
    return {
      appPrivateDir: pathApi.join(projectRootPath, ".runtime", "app-private"),
      dbPath: pathApi.join(projectRootPath, "data", "app.db"),
    };
  }

  const userDataPath = readAppPath(appApi, "userData");
  if (userDataPath) {
    return {
      appPrivateDir: pathApi.join(userDataPath, "app-private"),
      dbPath: pathApi.join(userDataPath, "data", "app.db"),
    };
  }

  return {
    appPrivateDir: pathApi.join(projectRootPath, ".runtime", "app-private"),
    dbPath: pathApi.join(projectRootPath, "data", "app.db"),
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

function buildLoadingWindowHtml() {
  return `data:text/html;charset=utf-8,<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${desktopAppDisplayName}</title></head><body style="margin:0;font-family:'Microsoft YaHei UI',sans-serif;background:#111317;color:#f3efe6;display:grid;place-items:center;height:100vh"><main style="max-width:560px;padding:32px;border:1px solid rgba(255,255,255,.1);border-radius:20px;background:rgba(255,255,255,.04);text-align:center"><h1 style="margin:0 0 12px">${desktopAppDisplayName}</h1><p style="margin:0;color:rgba(243,239,230,.82)">正在启动，请稍后...</p></main></body></html>`;
}


function createWindow({ mode = "app" } = {}) {
  const windowState = loadWindowState();

  if (!mainWindow) {
    mainWindow = new BrowserWindow({
      ...windowState,
      show: false,
      title: desktopAppDisplayName,
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
  }

  if (typeof mainWindow.setTitle === "function") {
    mainWindow.setTitle(desktopAppDisplayName);
  }

  if (mode === "loading") {
    mainWindow.loadURL(buildLoadingWindowHtml());
    return mainWindow;
  }

  mainWindow.loadFile(rendererEntryPath);
  return mainWindow;
}


function buildStartupFailureCopy(runtimeMode, { isPackaged = app?.isPackaged === true } = {}) {
  if (isPackaged || runtimeMode?.backendMode === "remote") {
    return "服务器连接失败，请稍后重试。";
  }

  return "Python 后端未能成功拉起，请先确认 .venv 与 data/app.db 是否存在。";
}


function shouldRevealStartupFailureDetails(runtimeMode, { isPackaged = app?.isPackaged === true } = {}) {
  return !isPackaged && runtimeMode?.backendMode !== "remote";
}


function createFailureWindow(
  error,
  runtimeMode,
  {
    BrowserWindowImpl = BrowserWindow,
    isPackaged = app?.isPackaged === true,
  } = {},
) {
  const message = encodeURIComponent(String(error instanceof Error ? error.message : error));
  const copy = encodeURIComponent(buildStartupFailureCopy(runtimeMode, { isPackaged }));
  const detailsHtml = shouldRevealStartupFailureDetails(runtimeMode, { isPackaged })
    ? `<pre style="white-space:pre-wrap;color:#ffb0b0">${message}</pre>`
    : "";
  const html = `data:text/html;charset=utf-8,<!doctype html><html lang="zh-CN"><body style="margin:0;font-family:'Microsoft YaHei UI',sans-serif;background:#111317;color:#f3efe6;display:grid;place-items:center;height:100vh"><main style="max-width:680px;padding:32px;border:1px solid rgba(255,255,255,.1);border-radius:20px;background:rgba(255,255,255,.04)"><h1 style="margin-top:0">C5 交易助手启动失败</h1><p>${copy}</p>${detailsHtml}</main></body></html>`;
  const failureWindow = mainWindow ?? new BrowserWindowImpl({
    width: 880,
    height: 620,
    backgroundColor: "#111317",
  });
  if (typeof failureWindow.setTitle === "function") {
    failureWindow.setTitle(desktopAppDisplayName);
  }
  failureWindow.loadURL(html);
  failureWindow.show?.();
  mainWindow = failureWindow;
}


async function bootstrapApplication({
  runtimeMode = resolveDesktopRuntimeMode(process.env),
  createFailureWindowImpl = createFailureWindow,
  createWindowImpl = createWindow,
  ensureBackendDependenciesImpl = ensureBackendDependencies,
  ensureWindowStateDependenciesImpl = ensureWindowStateDependencies,
  findAvailablePortImpl = findAvailablePort,
  readProgramAccessConfigImpl = readProgramAccessConfig,
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
      createWindowImpl({ mode: "app" });
      return;
    }

    createWindowImpl({ mode: "loading" });
    await ensureBackendDependenciesImpl();
    const port = await findAvailablePortImpl();
    const selectedResolvePythonExecutable = resolvePythonExecutableImpl ?? resolvePythonExecutable;
    const selectedStartPythonBackend = startPythonBackendImpl ?? startPythonBackend;
    const rawProgramAccessConfig = readProgramAccessConfigImpl({
      appApi: app,
    });
    const embeddedBackendPaths = resolveEmbeddedBackendPaths({
      appApi: app,
      projectRootPath: projectRoot,
    });
    const packagedRelease = app?.isPackaged === true;
    const controlPlaneBaseUrl = typeof rawProgramAccessConfig?.controlPlaneBaseUrl === "string"
      ? rawProgramAccessConfig.controlPlaneBaseUrl.trim()
      : "";
    if (packagedRelease && !controlPlaneBaseUrl) {
      throw new Error("Packaged release requires a control plane base url.");
    }
    const programAccessConfig = packagedRelease
      ? {
          ...rawProgramAccessConfig,
          appPrivateDir: embeddedBackendPaths.appPrivateDir,
          controlPlaneBaseUrl,
          stage: "packaged_release",
        }
      : rawProgramAccessConfig;
    const pythonExecutable = selectedResolvePythonExecutable(projectRoot);
    backend = await selectedStartPythonBackend({
      dbPath: embeddedBackendPaths.dbPath,
      pollIntervalMs: 250,
      portProvider: () => port,
      programAccessConfig,
      projectRoot,
      pythonExecutable,
      timeoutMs: 15000,
    });
    bootstrapConfig = {
      ...bootstrapConfig,
      apiBaseUrl: backend.baseUrl,
      backendStatus: "ready",
    };
    createWindowImpl({ mode: "app" });
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
  createFailureWindow,
  configureDesktopStoragePaths,
  deriveLocalAppDataRoot,
  migrateLegacySessionData,
  resolveEmbeddedBackendPaths,
  resolveDesktopStoragePaths,
};
