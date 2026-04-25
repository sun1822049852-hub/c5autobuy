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


async function isBackendHealthReady(response) {
  if (!response?.ok) {
    return false;
  }

  if (typeof response.json !== "function") {
    return true;
  }

  try {
    const payload = await response.json();
    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "ready")) {
      return payload.ready === true;
    }
  } catch {
    // Older callers may not expose a JSON health payload; keep the previous
    // "HTTP 200 means alive" fallback when the body cannot be parsed.
  }

  return true;
}


export function buildPythonBackendEnv(projectRoot, baseEnv = process.env, programAccessConfig = null) {
  const explicitAppPrivateDir = typeof programAccessConfig?.appPrivateDir === "string"
    ? programAccessConfig.appPrivateDir.trim()
    : "";
  const env = {
    ...baseEnv,
    C5_APP_PRIVATE_DIR: explicitAppPrivateDir || path.join(projectRoot, ".runtime", "app-private"),
  };

  const stage = typeof programAccessConfig?.stage === "string"
    ? programAccessConfig.stage.trim()
    : "";
  const controlPlaneBaseUrl = typeof programAccessConfig?.controlPlaneBaseUrl === "string"
    ? programAccessConfig.controlPlaneBaseUrl.trim()
    : "";
  const probeRegistrationReadiness = programAccessConfig?.probeRegistrationReadiness === true;
  if (stage) {
    env.C5_PROGRAM_ACCESS_STAGE = stage;
  }
  if (controlPlaneBaseUrl) {
    env.C5_PROGRAM_CONTROL_PLANE_BASE_URL = controlPlaneBaseUrl;
    if (!stage) {
      env.C5_PROGRAM_ACCESS_STAGE = "packaged_release";
    }
  }
  if (probeRegistrationReadiness) {
    env.C5_PROGRAM_ACCESS_PROBE_REGISTRATION_READINESS = "1";
  }
  if (env.C5_PROGRAM_ACCESS_STAGE === "packaged_release") {
    env.PYTHONNOUSERSITE = "1";
  }

  return env;
}


export async function startPythonBackend({
  projectRoot,
  dbPath,
  portProvider,
  pythonExecutable,
  programAccessConfig = null,
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
    env: buildPythonBackendEnv(projectRoot, process.env, programAccessConfig),
  });
  const baseUrl = `http://127.0.0.1:${port}`;
  const startedAt = Date.now();
  const stderrChunks = [];
  let earlyExitError = null;

  child.stdout?.on?.("data", () => {
    // Drain uvicorn access logs so the stdout pipe cannot fill and block the backend loop.
  });
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
        if (await isBackendHealthReady(response)) {
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
