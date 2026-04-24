import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { spawnSync } from "node:child_process";

import { getPackagedPythonRuntimeConfig } from "./python_runtime_config.cjs";


function buildManagedPythonRuntimePaths({
  appPrivateDir,
  arch = process.arch,
  pathApi = path,
  platform = process.platform,
  runtimeConfig = getPackagedPythonRuntimeConfig({ arch, platform }),
} = {}) {
  const normalizedAppPrivateDir = pathApi.resolve(String(appPrivateDir || ""));
  const runtimeRoot = pathApi.join(
    normalizedAppPrivateDir,
    runtimeConfig.runtimeRootDirName,
    runtimeConfig.version,
  );
  const archivePath = pathApi.join(
    normalizedAppPrivateDir,
    runtimeConfig.downloadsDirName,
    runtimeConfig.archiveFileName,
  );
  const stagingRoot = pathApi.join(
    normalizedAppPrivateDir,
    runtimeConfig.stagingDirName,
    `${runtimeConfig.version}-${runtimeConfig.arch}`,
  );
  const manifestPath = pathApi.join(runtimeRoot, runtimeConfig.manifestFileName);
  const pythonExecutable = pathApi.join(runtimeRoot, "python.exe");
  const pthPath = pathApi.join(runtimeRoot, runtimeConfig.pthFileName);
  const sitePackagesPath = pathApi.join(runtimeRoot, runtimeConfig.sitePackagesRelativePath);

  return {
    archivePath,
    manifestPath,
    pythonExecutable,
    pthPath,
    runtimeRoot,
    sitePackagesPath,
    stagingRoot,
  };
}


function isManagedRuntimeReusable({
  existsSync = fs.existsSync,
  manifestPath,
  pthPath,
  pythonExecutable,
  readFileSync = fs.readFileSync,
  runtimeConfig,
  sitePackagesPath,
}) {
  if (
    !existsSync(manifestPath)
    || !existsSync(pythonExecutable)
    || !existsSync(pthPath)
    || !existsSync(sitePackagesPath)
  ) {
    return false;
  }

  try {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    return manifest?.version === runtimeConfig.version && manifest?.sha256 === runtimeConfig.sha256;
  } catch {
    return false;
  }
}


async function downloadRuntimeArchive({
  abortControllerFactory = () => new AbortController(),
  archivePath,
  clearTimeoutImpl = clearTimeout,
  createWriteStream = fs.createWriteStream,
  fetchImpl = globalThis.fetch,
  mkdirSync = fs.mkdirSync,
  pipelineImpl = pipeline,
  runtimeConfig,
  setTimeoutImpl = setTimeout,
  timeoutMs = Number(runtimeConfig?.downloadTimeoutMs) > 0
    ? Number(runtimeConfig.downloadTimeoutMs)
    : 60000,
}) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Global fetch is unavailable for Python runtime download.");
  }

  mkdirSync(path.dirname(archivePath), {
    recursive: true,
  });
  const abortController = abortControllerFactory();
  const timeoutError = new Error(`Python runtime download timed out after ${timeoutMs}ms`);
  const timeoutHandle = setTimeoutImpl(() => {
    abortController.abort(timeoutError);
  }, timeoutMs);

  try {
    const response = await fetchImpl(runtimeConfig.url, {
      signal: abortController.signal,
    });
    if (!response?.ok || !response.body) {
      throw new Error(`Python runtime download failed: HTTP ${response?.status || "unknown"}`);
    }

    const fileStream = createWriteStream(archivePath);
    await pipelineImpl(Readable.fromWeb(response.body), fileStream);
    return {
      archivePath,
    };
  } catch (error) {
    if (abortController.signal.aborted && abortController.signal.reason === timeoutError) {
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeoutImpl(timeoutHandle);
  }
}


async function verifyRuntimeArchive({
  archivePath,
  runtimeConfig,
}) {
  const hash = crypto.createHash("sha256");
  await new Promise((resolve, reject) => {
    const stream = fs.createReadStream(archivePath);
    stream.on("data", (chunk) => {
      hash.update(chunk);
    });
    stream.on("error", reject);
    stream.on("end", resolve);
  });

  const digest = hash.digest("hex").toLowerCase();
  if (digest !== String(runtimeConfig.sha256).toLowerCase()) {
    throw new Error(`Python runtime checksum mismatch: expected ${runtimeConfig.sha256}, got ${digest}`);
  }
}


async function extractRuntimeArchive({
  archivePath,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  rmSync = fs.rmSync,
  spawnSyncImpl = spawnSync,
  stagingRoot,
}) {
  rmSync(stagingRoot, {
    force: true,
    recursive: true,
  });
  mkdirSync(stagingRoot, {
    recursive: true,
  });

  const result = spawnSyncImpl(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `Expand-Archive -LiteralPath ${JSON.stringify(archivePath)} -DestinationPath ${JSON.stringify(stagingRoot)} -Force`,
    ],
    {
      encoding: "utf8",
      stdio: "pipe",
      windowsHide: true,
    },
  );

  if (result?.error) {
    throw result.error;
  }
  if (typeof result?.status === "number" && result.status !== 0) {
    const details = String(result.stderr || result.stdout || "").trim() || `exit code ${result.status}`;
    throw new Error(`Python runtime extract failed: ${details}`);
  }

  return {
    extractedRuntimeRoot: stagingRoot,
    pythonExecutable: pathApi.join(stagingRoot, "python.exe"),
  };
}


function patchEmbeddableRuntime({
  copyFileSync = fs.copyFileSync,
  extractedRuntimeRoot,
  lstatSync = fs.lstatSync,
  mkdirSync = fs.mkdirSync,
  packagedPythonDepsPath,
  pathApi = path,
  projectRoot = "",
  readFileSync = fs.readFileSync,
  readdirSync = fs.readdirSync,
  runtimeConfig,
  writeFileSync = fs.writeFileSync,
} = {}) {
  const sourceSitePackagesPath = pathApi.join(packagedPythonDepsPath, runtimeConfig.sitePackagesRelativePath);
  const targetSitePackagesPath = pathApi.join(extractedRuntimeRoot, runtimeConfig.sitePackagesRelativePath);
  mkdirSync(targetSitePackagesPath, {
    recursive: true,
  });
  try {
    copyPathRecursive({
      copyFileSync,
      lstatSync,
      mkdirSync,
      pathApi,
      readdirSync,
      sourcePath: sourceSitePackagesPath,
      targetPath: targetSitePackagesPath,
    });
  } catch (error) {
    throw new Error(`Failed to install packaged Python dependencies from ${sourceSitePackagesPath}: ${error instanceof Error ? error.message : String(error)}`);
  }

  const pthPath = pathApi.join(extractedRuntimeRoot, runtimeConfig.pthFileName);
  let existingLines = [];
  try {
    existingLines = String(readFileSync(pthPath, "utf8")).split(/\r?\n/);
  } catch {
    existingLines = [];
  }
  const normalizedProjectRoot = typeof projectRoot === "string"
    ? projectRoot.trim().replace(/\\/g, "/")
    : "";
  const normalizedSitePackagesLine = String(runtimeConfig.sitePackagesRelativePath).replace(/\\/g, "/");
  const filteredLines = existingLines
    .map((line) => line.trim())
    .filter((line) => (
      line
      && line !== "import site"
      && line !== "#import site"
      && line.replace(/\\/g, "/") !== normalizedSitePackagesLine
      && line.replace(/\\/g, "/") !== normalizedProjectRoot
    ));
  const nextLines = [];
  for (const line of [
    ...filteredLines,
    ".",
    normalizedProjectRoot,
    normalizedSitePackagesLine,
  ]) {
    const normalizedLine = String(line || "").trim();
    if (!normalizedLine || nextLines.includes(normalizedLine)) {
      continue;
    }
    nextLines.push(normalizedLine);
  }
  nextLines.push("");
  writeFileSync(pthPath, nextLines.join("\n"), "utf8");
}


function copyPathRecursive({
  copyFileSync = fs.copyFileSync,
  lstatSync = fs.lstatSync,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  readdirSync = fs.readdirSync,
  sourcePath,
  targetPath,
}) {
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


async function finalizeManagedRuntime({
  archivePath,
  extractedRuntimeRoot,
  manifestPath,
  mkdirSync = fs.mkdirSync,
  pathApi = path,
  removePathImpl = (targetPath) => {
    fs.rmSync(targetPath, {
      force: true,
      recursive: true,
    });
  },
  renameSync = fs.renameSync,
  runtimeConfig,
  runtimeRoot,
  writeFileSync = fs.writeFileSync,
}) {
  removePathImpl(runtimeRoot);
  mkdirSync(pathApi.dirname(runtimeRoot), {
    recursive: true,
  });
  if (extractedRuntimeRoot !== runtimeRoot) {
    renameSync(extractedRuntimeRoot, runtimeRoot);
  }

  writeFileSync(manifestPath, JSON.stringify({
    installedAt: new Date().toISOString(),
    sha256: runtimeConfig.sha256,
    sourceUrl: runtimeConfig.url,
    version: runtimeConfig.version,
  }, null, 2), "utf8");
  if (archivePath) {
    removePathImpl(archivePath);
  }

  return {
    pythonExecutable: pathApi.join(runtimeRoot, "python.exe"),
    runtimeRoot,
  };
}


export async function ensureManagedPythonRuntime({
  appPrivateDir,
  arch = process.arch,
  downloadRuntimeArchiveImpl = null,
  existsSync = fs.existsSync,
  extractRuntimeArchiveImpl = extractRuntimeArchive,
  finalizeManagedRuntimeImpl = finalizeManagedRuntime,
  installPackagedPythonDepsImpl = patchEmbeddableRuntime,
  packagedPythonDepsPath,
  pathApi = path,
  platform = process.platform,
  projectRoot = "",
  readFileSync = fs.readFileSync,
  removePathImpl = (targetPath) => {
    fs.rmSync(targetPath, {
      force: true,
      recursive: true,
    });
  },
  runtimeConfig = getPackagedPythonRuntimeConfig({ arch, platform }),
  verifyRuntimeArchiveImpl = verifyRuntimeArchive,
} = {}) {
  const managedPaths = buildManagedPythonRuntimePaths({
    appPrivateDir,
    arch,
    pathApi,
    platform,
    runtimeConfig,
  });

  if (isManagedRuntimeReusable({
    existsSync,
    manifestPath: managedPaths.manifestPath,
    pthPath: managedPaths.pthPath,
    pythonExecutable: managedPaths.pythonExecutable,
    readFileSync,
    runtimeConfig,
    sitePackagesPath: managedPaths.sitePackagesPath,
  })) {
    return {
      pythonExecutable: managedPaths.pythonExecutable,
      runtimeRoot: managedPaths.runtimeRoot,
    };
  }

  const runtimeArchiveDownloader = downloadRuntimeArchiveImpl || (async ({ archivePath, runtimeConfig: config }) => downloadRuntimeArchive({
    archivePath,
    runtimeConfig: config,
  }));

  let downloadResult;
  try {
    downloadResult = await runtimeArchiveDownloader({
      archivePath: managedPaths.archivePath,
      projectRoot,
      runtimeConfig,
    });
  } catch (error) {
    removePathImpl(managedPaths.archivePath);
    throw error;
  }
  const archivePath = downloadResult?.archivePath || managedPaths.archivePath;

  try {
    await verifyRuntimeArchiveImpl({
      archivePath,
      runtimeConfig,
    });
  } catch (error) {
    removePathImpl(archivePath);
    throw error;
  }

  let extractedRuntimeRoot = "";
  try {
    const extractResult = await extractRuntimeArchiveImpl({
      archivePath,
      projectRoot,
      runtimeConfig,
      stagingRoot: managedPaths.stagingRoot,
    });
    extractedRuntimeRoot = extractResult?.extractedRuntimeRoot || managedPaths.stagingRoot;

    await installPackagedPythonDepsImpl({
      extractedRuntimeRoot,
      packagedPythonDepsPath,
      projectRoot,
      runtimeConfig,
    });

    return await finalizeManagedRuntimeImpl({
      archivePath,
      extractedRuntimeRoot,
      manifestPath: managedPaths.manifestPath,
      removePathImpl,
      runtimeConfig,
      runtimeRoot: managedPaths.runtimeRoot,
    });
  } catch (error) {
    if (extractedRuntimeRoot) {
      removePathImpl(extractedRuntimeRoot);
    }
    throw error;
  }
}


export {
  buildManagedPythonRuntimePaths,
  downloadRuntimeArchive,
  patchEmbeddableRuntime,
};
