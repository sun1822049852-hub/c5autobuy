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
  const dbPathLiteral = JSON.stringify(String(dbPath));
  const launchScript = [
    "from pathlib import Path;",
    "from app_backend.main import main;",
    `main(db_path=Path(${dbPathLiteral}), host='127.0.0.1', port=${port})`,
  ].join(" ");
  return [
    "-c",
    launchScript,
  ];
}


function buildBackendExitError({ code, signal, stderrOutput }) {
  const details = [];
  if (code !== null && code !== undefined) {
    details.push(`exit code ${code}`);
  }
  if (signal) {
    details.push(`signal ${signal}`);
  }

  const detailSuffix = details.length ? ` (${details.join(", ")})` : "";
  const stderrSuffix = stderrOutput ? `: ${stderrOutput}` : "";
  return new Error(`Python backend exited before becoming healthy${detailSuffix}${stderrSuffix}`);
}


function buildPythonBackendEnv(projectRoot, baseEnv = process.env) {
  return {
    ...baseEnv,
    C5_APP_PRIVATE_DIR: path.join(projectRoot, ".runtime", "app-private"),
  };
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
    env: buildPythonBackendEnv(projectRoot),
  });
  const baseUrl = `http://127.0.0.1:${port}`;
  const startedAt = Date.now();
  const stderrChunks = [];
  let earlyExitError = null;

  child.stderr?.on?.("data", (chunk) => {
    stderrChunks.push(Buffer.isBuffer(chunk) ? chunk.toString("utf-8") : String(chunk));
  });
  child.once?.("error", (error) => {
    earlyExitError = error instanceof Error ? error : new Error(String(error));
  });
  child.once?.("exit", (code, signal) => {
    earlyExitError = buildBackendExitError({
      code,
      signal,
      stderrOutput: stderrChunks.join("").trim(),
    });
  });

  try {
    while (Date.now() - startedAt <= timeoutMs) {
      if (earlyExitError) {
        throw earlyExitError;
      }
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
      if (earlyExitError) {
        throw earlyExitError;
      }
      await sleep(pollIntervalMs);
    }
  } catch (error) {
    if (error !== earlyExitError) {
      child.kill();
    }
    throw error;
  }

  if (earlyExitError) {
    throw earlyExitError;
  }
  child.kill();
  throw new Error("等待本地后端启动超时");
}


function defaultSpawnProcess({ command, args, cwd, env }) {
  return spawn(command, args, {
    cwd,
    env,
    stdio: "pipe",
    windowsHide: true,
  });
}
