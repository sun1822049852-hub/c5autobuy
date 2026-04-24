const path = require("node:path");


const EXCLUDED_TOP_LEVEL_ENTRIES = Object.freeze([
  "PySide6",
  "shiboken6",
  "pytest",
  "_pytest",
  "pip",
  "setuptools",
  "wheel",
  "pygments",
  "pluggy",
  "iniconfig",
]);

const EMBEDDABLE_TARGETS = Object.freeze({
  x64: Object.freeze({
    arch: "x64",
    id: "pythonembed-3.11-64",
    version: "3.11.9",
    url: "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embeddable-amd64.zip",
    sha256: "33b448f95fecb7c6f802157dbd5e6b40a2ad9bfc8b95ca634a06ba4073ad1ac0",
    pthFileName: "python311._pth",
  }),
  arm64: Object.freeze({
    arch: "arm64",
    id: "pythonembed-3.11-arm64",
    version: "3.11.9",
    url: "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embeddable-arm64.zip",
    sha256: "d1db9bced6c6b4268f5afe2365c818dd540d97b2501865502abea4bc527e933e",
    pthFileName: "python311._pth",
  }),
});


function normalizeRuntimeArch(arch) {
  if (arch === "arm64") {
    return "arm64";
  }
  if (arch === "x64") {
    return "x64";
  }
  throw new Error(`Unsupported packaged Python runtime arch: ${arch}`);
}


function getPackagedPythonRuntimeConfig({
  arch = process.arch,
  platform = process.platform,
} = {}) {
  if (platform !== "win32") {
    throw new Error(`Packaged Python runtime bootstrap only supports Windows: ${platform}`);
  }

  const normalizedArch = normalizeRuntimeArch(arch);
  const target = EMBEDDABLE_TARGETS[normalizedArch];
  return Object.freeze({
    ...target,
    archiveFileName: path.basename(target.url),
    downloadTimeoutMs: 60000,
    downloadsDirName: "python-runtime-downloads",
    excludedTopLevelEntries: EXCLUDED_TOP_LEVEL_ENTRIES,
    manifestFileName: "runtime-manifest.json",
    pythonDepsDirName: "python_deps",
    runtimeRootDirName: "python-runtime",
    sitePackagesRelativePath: path.join("Lib", "site-packages"),
    stagingDirName: ".python-runtime-staging",
  });
}


module.exports = {
  getPackagedPythonRuntimeConfig,
};
