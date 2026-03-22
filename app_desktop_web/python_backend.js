import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";


function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}


function getPythonRelativePath(platform = process.platform) {
  return platform === "win32"
    ? path.join(".venv", "Scripts", "python.exe")
    : path.join(".venv", "bin", "python");
}


export function resolvePythonExecutable(
  projectRoot,
  {
    existsSync = fs.existsSync,
    platform = process.platform,
  } = {},
) {
  const pythonRelativePath = getPythonRelativePath(platform);
  let currentDirectory = path.resolve(projectRoot);

  while (true) {
    const candidatePath = path.join(currentDirectory, pythonRelativePath);
    if (existsSync(candidatePath)) {
      return candidatePath;
    }

    const parentDirectory = path.dirname(currentDirectory);
    if (parentDirectory === currentDirectory) {
      return path.join(path.resolve(projectRoot), pythonRelativePath);
    }

    currentDirectory = parentDirectory;
  }
}


export function buildPythonLaunchArgs({ projectRoot, dbPath, port }) {
  void projectRoot;
  return [
    "-c",
    `from pathlib import Path; from app_backend.main import main; main(db_path=Path(r'${dbPath}'), host='127.0.0.1', port=${port})`,
  ];
}


export async function startPythonBackend({
  projectRoot,
  dbPath,
  portProvider,
  pythonExecutable,
  spawnProcess = defaultSpawnProcess,
  fetchImpl = globalThis.fetch,
  pollIntervalMs = 250,
  timeoutMs = 10000,
}) {
  const port = Number(portProvider());
  const args = buildPythonLaunchArgs({ projectRoot, dbPath, port });
  const child = spawnProcess({
    command: pythonExecutable,
    args,
    cwd: projectRoot,
  });
  const baseUrl = `http://127.0.0.1:${port}`;
  const startedAt = Date.now();

  try {
    while (Date.now() - startedAt <= timeoutMs) {
      try {
        const response = await fetchImpl(`${baseUrl}/health`);
        if (response?.ok) {
          return {
            process: child,
            port,
            baseUrl,
            stop() {
              child.kill();
            },
          };
        }
      } catch (_error) {
        // Ignore connection failures until timeout; health polling is the readiness gate.
      }
      await sleep(pollIntervalMs);
    }
  } catch (error) {
    child.kill();
    throw error;
  }

  child.kill();
  throw new Error("等待本地后端启动超时");
}


function defaultSpawnProcess({ command, args, cwd }) {
  return spawn(command, args, {
    cwd,
    stdio: "pipe",
    windowsHide: true,
  });
}
