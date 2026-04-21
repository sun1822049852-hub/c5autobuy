const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const { resolveBundledResourcePath } = require("./electron-builder-paths.cjs");
const { ensureRendererBuild } = require("../main_ui_node_desktop.js");


function resolveBundledPythonExecutable({
  appDir = __dirname,
  existsSync = fs.existsSync,
  pathApi = path,
  platform = process.platform,
} = {}) {
  const bundledVenvPath = resolveBundledResourcePath({
    appDir,
    existsSync,
    resourcePath: ".venv",
  });
  const pythonRelativePath = platform === "win32"
    ? pathApi.join("Scripts", "python.exe")
    : pathApi.join("bin", "python");

  return pathApi.join(bundledVenvPath, pythonRelativePath);
}


function verifyEmbeddedPythonRuntime({
  appDir = __dirname,
  env = process.env,
  existsSync = fs.existsSync,
  pathApi = path,
  platform = process.platform,
  spawnSync: spawnSyncImpl = spawnSync,
} = {}) {
  const pythonExecutable = resolveBundledPythonExecutable({
    appDir,
    existsSync,
    pathApi,
    platform,
  });
  const bundledBackendPath = resolveBundledResourcePath({
    appDir,
    existsSync,
    resourcePath: "app_backend",
  });
  const workspaceRoot = pathApi.dirname(bundledBackendPath);

  if (!existsSync(pythonExecutable)) {
    throw new Error(`Embedded Python runtime not found: ${pythonExecutable}`);
  }
  if (!existsSync(bundledBackendPath)) {
    throw new Error(`Bundled backend source not found: ${bundledBackendPath}`);
  }

  const importProbe = [
    "from app_backend.main import main",
    "print('embedded-python-runtime-ok')",
  ].join("; ");
  const result = spawnSyncImpl(
    pythonExecutable,
    ["-c", importProbe],
    {
      cwd: workspaceRoot,
      encoding: "utf8",
      env,
      stdio: "pipe",
    },
  );

  if (result?.error) {
    throw result.error;
  }
  if (typeof result?.status === "number" && result.status !== 0) {
    const stderrOutput = String(result.stderr || result.stdout || "").trim();
    const details = stderrOutput || `exit code ${result.status}`;
    throw new Error(`Embedded Python runtime preflight failed: ${details}`);
  }

  return {
    pythonExecutable,
    workspaceRoot,
  };
}


function ensurePackagingPrerequisites({
  appDir = __dirname,
  ensureRendererBuildImpl = ensureRendererBuild,
  verifyEmbeddedPythonRuntimeImpl = verifyEmbeddedPythonRuntime,
} = {}) {
  ensureRendererBuildImpl(appDir);
  return verifyEmbeddedPythonRuntimeImpl({
    appDir,
  });
}


if (require.main === module) {
  try {
    const { pythonExecutable, workspaceRoot } = ensurePackagingPrerequisites({
      appDir: __dirname,
    });
    console.log(`Embedded Python runtime preflight passed: ${pythonExecutable} (cwd: ${workspaceRoot})`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  }
}


module.exports = {
  ensurePackagingPrerequisites,
  resolveBundledPythonExecutable,
  verifyEmbeddedPythonRuntime,
};
