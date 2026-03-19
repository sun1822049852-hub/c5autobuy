import path from "node:path";
import { fileURLToPath } from "node:url";
import net from "node:net";

import { loadElectronMainApis } from "./electron_runtime.js";
import { startPythonBackend } from "./python_backend.js";
import { loadWindowState, saveWindowState } from "./window_state.js";


const { app, BrowserWindow, ipcMain } = loadElectronMainApis();
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const rendererEntryPath = path.join(__dirname, "dist", "index.html");
const pythonExecutable = path.join(projectRoot, ".venv", "Scripts", "python.exe");
const dbPath = path.join(projectRoot, "data", "app.db");
let mainWindow = null;
let backend = null;
let bootstrapConfig = {
  apiBaseUrl: "",
  backendStatus: "starting",
};


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
      preload: path.join(__dirname, "electron-preload.js"),
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


function createFailureWindow(error) {
  const message = encodeURIComponent(String(error instanceof Error ? error.message : error));
  const html = `data:text/html;charset=utf-8,<!doctype html><html lang="zh-CN"><body style="margin:0;font-family:'Microsoft YaHei UI',sans-serif;background:#111317;color:#f3efe6;display:grid;place-items:center;height:100vh"><main style="max-width:680px;padding:32px;border:1px solid rgba(255,255,255,.1);border-radius:20px;background:rgba(255,255,255,.04)"><h1 style="margin-top:0">账号中心桌面端启动失败</h1><p>Python 后端未能成功拉起，请先确认 <code>.venv</code> 与 <code>data/app.db</code> 是否存在。</p><pre style="white-space:pre-wrap;color:#ffb0b0">${message}</pre></main></body></html>`;
  const failureWindow = new BrowserWindow({
    width: 880,
    height: 620,
    backgroundColor: "#111317",
  });
  failureWindow.loadURL(html);
}


async function bootstrapApplication() {
  try {
    const port = await findAvailablePort();
    backend = await startPythonBackend({
      dbPath,
      pollIntervalMs: 250,
      portProvider: () => port,
      projectRoot,
      pythonExecutable,
      timeoutMs: 15000,
    });
    bootstrapConfig = {
      apiBaseUrl: backend.baseUrl,
      backendStatus: "ready",
    };
    createWindow();
  } catch (error) {
    bootstrapConfig = {
      apiBaseUrl: "",
      backendStatus: "failed",
    };
    createFailureWindow(error);
  }
}


ipcMain.on("desktop:get-bootstrap-config", (event) => {
  event.returnValue = bootstrapConfig;
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

app.on("activate", () => {
  if (!BrowserWindow.getAllWindows().length && bootstrapConfig.backendStatus === "ready") {
    createWindow();
  }
});
