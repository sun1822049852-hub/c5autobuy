const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const { resolveBundledResourcePath } = require("./electron-builder-paths.cjs");
const { getPackagedPythonRuntimeConfig } = require("./python_runtime_config.cjs");


function resolveDevelopmentPythonExecutable({
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


function resolvePackagedPythonDepsPath({
  appDir = __dirname,
  pathApi = path,
} = {}) {
  return pathApi.join(pathApi.resolve(appDir), "build", "python_deps");
}


function shouldExcludePythonDependencyEntry(entryName, excludedTopLevelEntries) {
  const normalizedName = String(entryName || "").trim().toLowerCase();
  if (!normalizedName) {
    return true;
  }

  return excludedTopLevelEntries.some((entry) => (
    normalizedName === entry.toLowerCase()
    || normalizedName.startsWith(`${entry.toLowerCase()}-`)
    || normalizedName.startsWith(`${entry.toLowerCase()}.`)
  ));
}


function buildCopyFilter(sourcePath) {
  const normalizedPath = String(sourcePath || "").replace(/\\/g, "/").toLowerCase();
  if (normalizedPath.includes("/__pycache__/")) {
    return false;
  }
  if (normalizedPath.includes("/.pytest_cache/")) {
    return false;
  }
  if (normalizedPath.endsWith(".pyc")) {
    return false;
  }
  return true;
}


function copyPathRecursive({
  copyFileSync = fs.copyFileSync,
  filter = () => true,
  lstatSync = fs.lstatSync,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  readdirSync = fs.readdirSync,
  sourcePath,
  targetPath,
}) {
  if (!filter(sourcePath)) {
    return;
  }

  const sourceStat = lstatSync(sourcePath);
  if (sourceStat.isDirectory()) {
    mkdirSync(targetPath, {
      recursive: true,
    });
    const childEntries = readdirSync(sourcePath, {
      withFileTypes: true,
    });
    for (const childEntry of childEntries) {
      copyPathRecursive({
        copyFileSync,
        filter,
        lstatSync,
        mkdirSync,
        pathApi,
        readdirSync,
        sourcePath: pathApi.join(sourcePath, childEntry.name),
        targetPath: pathApi.join(targetPath, childEntry.name),
      });
    }
    return;
  }

  mkdirSync(pathApi.dirname(targetPath), {
    recursive: true,
  });
  copyFileSync(sourcePath, targetPath);
}


function preparePackagedPythonResources({
  appDir = __dirname,
  arch = process.arch,
  copyFileSync = fs.copyFileSync,
  existsSync = fs.existsSync,
  lstatSync = fs.lstatSync,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  platform = process.platform,
  readdirSync = fs.readdirSync,
  rmSync = fs.rmSync,
} = {}) {
  const runtimeConfig = getPackagedPythonRuntimeConfig({
    arch,
    platform,
  });
  const pythonExecutable = resolveDevelopmentPythonExecutable({
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
  const sourceSitePackagesPath = resolveBundledResourcePath({
    appDir,
    existsSync,
    resourcePath: pathApi.join(".venv", "Lib", "site-packages"),
  });
  const pythonDepsPath = resolvePackagedPythonDepsPath({
    appDir,
    pathApi,
  });
  const outputSitePackagesPath = pathApi.join(pythonDepsPath, runtimeConfig.sitePackagesRelativePath);

  if (!existsSync(pythonExecutable)) {
    throw new Error(`Development Python runtime not found: ${pythonExecutable}`);
  }
  if (!existsSync(sourceSitePackagesPath)) {
    throw new Error(`Development site-packages not found: ${sourceSitePackagesPath}`);
  }
  if (!existsSync(bundledBackendPath)) {
    throw new Error(`Bundled backend source not found: ${bundledBackendPath}`);
  }

  rmSync(pythonDepsPath, {
    force: true,
    recursive: true,
  });
  mkdirSync(outputSitePackagesPath, {
    recursive: true,
  });

  const topLevelEntries = readdirSync(sourceSitePackagesPath, {
    withFileTypes: true,
  });
  for (const entry of topLevelEntries) {
    if (shouldExcludePythonDependencyEntry(entry.name, runtimeConfig.excludedTopLevelEntries)) {
      continue;
    }

    const sourcePath = pathApi.join(sourceSitePackagesPath, entry.name);
    const targetPath = pathApi.join(outputSitePackagesPath, entry.name);
    copyPathRecursive({
      copyFileSync,
      filter: buildCopyFilter,
      lstatSync,
      mkdirSync,
      pathApi,
      readdirSync,
      sourcePath,
      targetPath,
    });
  }

  return {
    outputSitePackagesPath,
    pythonDepsPath,
    pythonExecutable,
    runtimeConfig,
    workspaceRoot: pathApi.dirname(bundledBackendPath),
  };
}


function verifyPackagedPythonResources({
  appDir = __dirname,
  arch = process.arch,
  env = process.env,
  existsSync = fs.existsSync,
  pathApi = path,
  platform = process.platform,
  preparedResources = null,
  spawnSync: spawnSyncImpl = spawnSync,
} = {}) {
  const runtimeConfig = getPackagedPythonRuntimeConfig({
    arch,
    platform,
  });
  const prepared = preparedResources || preparePackagedPythonResources({
    appDir,
    arch,
    existsSync,
    pathApi,
    platform,
  });
  const outputSitePackagesPath = prepared.outputSitePackagesPath
    || pathApi.join(prepared.pythonDepsPath, runtimeConfig.sitePackagesRelativePath);
  const workspaceRoot = prepared.workspaceRoot;
  const pythonExecutable = prepared.pythonExecutable || resolveDevelopmentPythonExecutable({
    appDir,
    existsSync,
    pathApi,
    platform,
  });

  if (!existsSync(outputSitePackagesPath)) {
    throw new Error(`Packaged Python dependency root not found: ${outputSitePackagesPath}`);
  }

  const importProbe = [
    "import sys",
    `sys.path[:0] = [${JSON.stringify(outputSitePackagesPath)}, ${JSON.stringify(workspaceRoot)}]`,
    "from app_backend.main import main",
    "print('packaged-python-resources-ok')",
  ].join("; ");
  const result = spawnSyncImpl(
    pythonExecutable,
    [
      "-S",
      "-c",
      importProbe,
    ],
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
    throw new Error(`Packaged Python resources preflight failed: ${details}`);
  }

  return {
    dependencyRoot: prepared.pythonDepsPath,
    outputSitePackagesPath,
    workspaceRoot,
  };
}


module.exports = {
  preparePackagedPythonResources,
  resolveDevelopmentPythonExecutable,
  resolvePackagedPythonDepsPath,
  verifyPackagedPythonResources,
};
