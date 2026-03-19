import { afterEach, describe, expect, it, vi } from "vitest";

import { buildPythonLaunchArgs, startPythonBackend } from "../../python_backend.js";

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
      "from pathlib import Path; from app_backend.main import main; main(db_path=Path(r'C:/demo/project/data/app.db'), host='127.0.0.1', port=8133)",
    ]);
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

    expect(spawnProcess).toHaveBeenCalledWith({
      command: "C:/demo/project/.venv/Scripts/python.exe",
      args: [
        "-c",
        "from pathlib import Path; from app_backend.main import main; main(db_path=Path(r'C:/demo/project/data/app.db'), host='127.0.0.1', port=8133)",
      ],
      cwd: "C:/demo/project",
    });
    expect(fetchImpl).toHaveBeenCalledWith("http://127.0.0.1:8133/health");
    expect(backend.baseUrl).toBe("http://127.0.0.1:8133");
    expect(backend.port).toBe(8133);

    backend.stop();
    expect(fakeChild.kill).toHaveBeenCalledWith();
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
});
