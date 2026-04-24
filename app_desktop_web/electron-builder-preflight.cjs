const fs = require("node:fs");
const path = require("node:path");
const {
  preparePackagedPythonResources,
  verifyPackagedPythonResources,
} = require("./python_runtime_resources.cjs");
const { ensureRendererBuild } = require("../main_ui_node_desktop.js");


function ensurePackagingPrerequisites({
  appDir = __dirname,
  ensureRendererBuildImpl = ensureRendererBuild,
  preparePackagedPythonResourcesImpl = preparePackagedPythonResources,
  verifyPackagedPythonResourcesImpl = verifyPackagedPythonResources,
} = {}) {
  ensureRendererBuildImpl(appDir);
  const preparedResources = preparePackagedPythonResourcesImpl({
    appDir,
  });
  return verifyPackagedPythonResourcesImpl({
    appDir,
    preparedResources,
  });
}


if (require.main === module) {
  try {
    const { dependencyRoot, workspaceRoot } = ensurePackagingPrerequisites({
      appDir: __dirname,
    });
    console.log(`Packaged Python resources preflight passed: ${dependencyRoot} (cwd: ${workspaceRoot})`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  }
}


module.exports = {
  ensurePackagingPrerequisites,
  preparePackagedPythonResources,
  verifyPackagedPythonResources,
};
