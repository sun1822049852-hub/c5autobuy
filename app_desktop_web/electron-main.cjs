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
};
