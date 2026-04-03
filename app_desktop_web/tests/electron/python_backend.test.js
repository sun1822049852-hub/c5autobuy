import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildPythonLaunchArgs,
  resolvePythonExecutable,
  startPythonBackend,
} from "../../python_backend.js";

function buildExpectedLaunchScript(dbPath, port) {
  return [
    "from pathlib import Path;",
    "from app_backend.main import main;",
    `main(db_path=Path(${JSON.stringify(dbPath)}), host='127.0.0.1', port=${port})`,
  ].join(" ");
}

function buildExpectedAppPrivateDir(projectRoot) {
  return path.join(projectRoot, ".runtime", "app-private");
}

describe("python backend manager", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("builds python launch args from project root, db path and selected port", () => {
    const args = buildPythonLaunchArgs({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      port: 8133,
    });

    expect(args).toEqual([
      "-c",
      buildExpectedLaunchScript("C:/demo/project/data/app.db", 8133),
    ]);
  });

  it("escapes database paths that contain single quotes when building python launch args", () => {
    const args = buildPythonLaunchArgs({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/O'Brien/data/app.db",
      port: 8133,
    });

    expect(args).toEqual([
      "-c",
      buildExpectedLaunchScript("C:/demo/O'Brien/data/app.db", 8133),
    ]);
  });

  it("falls back to an ancestor virtualenv when the worktree does not contain one", () => {
    const projectRoot = path.join("C:", "demo", "project", ".worktrees", "stats-ui");
    const expectedPython = path.join("C:", "demo", "project", ".venv", "Scripts", "python.exe");
    const existsSync = vi.fn((targetPath) => targetPath === expectedPython);

    const pythonExecutable = resolvePythonExecutable(projectRoot, {
      existsSync,
      platform: "win32",
    });

    expect(pythonExecutable).toBe(expectedPython);
  });

  it("starts python and resolves once health check passes", async () => {
    const fakeChild = {
      once: vi.fn(),
      kill: vi.fn(),
    };
    const spawnProcess = vi.fn(() => fakeChild);
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new Error("connect ECONNREFUSED"))
      .mockResolvedValueOnce({ ok: true });

    const backend = await startPythonBackend({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      portProvider: () => 8133,
      pythonExecutable: "C:/demo/project/.venv/Scripts/python.exe",
      spawnProcess,
      fetchImpl,
      pollIntervalMs: 1,
      timeoutMs: 50,
    });

    expect(spawnProcess).toHaveBeenCalledWith(expect.objectContaining({
      command: "C:/demo/project/.venv/Scripts/python.exe",
      args: [
        "-c",
        buildExpectedLaunchScript("C:/demo/project/data/app.db", 8133),
      ],
      cwd: "C:/demo/project",
      env: expect.objectContaining({
        C5_APP_PRIVATE_DIR: buildExpectedAppPrivateDir("C:/demo/project"),
      }),
    }));
    expect(fetchImpl).toHaveBeenCalledWith("http://127.0.0.1:8133/health");
    expect(backend.baseUrl).toBe("http://127.0.0.1:8133");
    expect(backend.port).toBe(8133);

    backend.stop();
    expect(fakeChild.kill).toHaveBeenCalledWith();
  });

  it("passes the app-private directory to the python child environment", async () => {
    const fakeChild = {
      once: vi.fn(),
      kill: vi.fn(),
    };
    const spawnProcess = vi.fn(() => fakeChild);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });

    await startPythonBackend({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      portProvider: () => 8233,
      pythonExecutable: "C:/demo/project/.venv/Scripts/python.exe",
      spawnProcess,
      fetchImpl,
      pollIntervalMs: 1,
      timeoutMs: 50,
    });

    expect(spawnProcess).toHaveBeenCalledWith(expect.objectContaining({
      env: expect.objectContaining({
        C5_APP_PRIVATE_DIR: buildExpectedAppPrivateDir("C:/demo/project"),
      }),
    }));
  });

  it("drains backend stdout so the access log pipe cannot block the backend loop", async () => {
    const stdoutListeners = new Map();
    const fakeChild = {
      once: vi.fn(),
      stdout: {
        on: vi.fn((eventName, handler) => {
          stdoutListeners.set(eventName, handler);
        }),
      },
      kill: vi.fn(),
    };
    const spawnProcess = vi.fn(() => fakeChild);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });

    await startPythonBackend({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      portProvider: () => 8234,
      pythonExecutable: "C:/demo/project/.venv/Scripts/python.exe",
      spawnProcess,
      fetchImpl,
      pollIntervalMs: 1,
      timeoutMs: 50,
    });

    expect(fakeChild.stdout.on).toHaveBeenCalledWith("data", expect.any(Function));
    expect(stdoutListeners.has("data")).toBe(true);
  });

  it("kills python and throws when health check times out", async () => {
    vi.useFakeTimers();

    const fakeChild = {
      once: vi.fn(),
      kill: vi.fn(),
    };
    const spawnProcess = vi.fn(() => fakeChild);
    const fetchImpl = vi.fn().mockRejectedValue(new Error("connect ECONNREFUSED"));

    const pending = startPythonBackend({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      portProvider: () => 9133,
      pythonExecutable: "C:/demo/project/.venv/Scripts/python.exe",
      spawnProcess,
      fetchImpl,
      pollIntervalMs: 10,
      timeoutMs: 40,
    });
    const rejection = expect(pending).rejects.toThrow("等待本地后端启动超时");

    await vi.advanceTimersByTimeAsync(60);

    await rejection;
    expect(fakeChild.kill).toHaveBeenCalledWith();
  });

  it("surfaces an early python process exit before the health check times out", async () => {
    vi.useFakeTimers();

    const childListeners = new Map();
    const stderrListeners = new Map();
    const fakeChild = {
      once: vi.fn((eventName, handler) => {
        childListeners.set(eventName, handler);
      }),
      stderr: {
        on: vi.fn((eventName, handler) => {
          stderrListeners.set(eventName, handler);
        }),
      },
      kill: vi.fn(),
    };
    const spawnProcess = vi.fn(() => fakeChild);
    const fetchImpl = vi.fn().mockRejectedValue(new Error("connect ECONNREFUSED"));

    const pending = startPythonBackend({
      projectRoot: "C:/demo/project",
      dbPath: "C:/demo/project/data/app.db",
      portProvider: () => 9133,
      pythonExecutable: "C:/demo/project/.venv/Scripts/python.exe",
      spawnProcess,
      fetchImpl,
      pollIntervalMs: 10,
      timeoutMs: 1000,
    });
    const rejection = expect(pending).rejects.toThrow("backend exploded");

    stderrListeners.get("data")?.(Buffer.from("backend exploded"));
    childListeners.get("exit")?.(2, null);
    await vi.advanceTimersByTimeAsync(20);

    await rejection;
    expect(fakeChild.kill).not.toHaveBeenCalled();
  });
});
