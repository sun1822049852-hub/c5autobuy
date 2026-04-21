const fs = require("node:fs");
const path = require("node:path");


function isPlainObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function normalizeUrl(value) {
  return typeof value === "string" ? value.trim() : "";
}

function readJsonObject(targetPath, { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = {}) {
  const normalizedPath = typeof targetPath === "string" ? targetPath.trim() : "";
  if (!normalizedPath || !existsSync(normalizedPath)) {
    return {};
  }

  try {
    const payload = JSON.parse(readFileSync(normalizedPath, "utf8"));
    return isPlainObject(payload) ? payload : {};
  } catch {
    return {};
  }
}

function resolveConfigCandidates({
  appApi = null,
  env = process.env,
  moduleDir = __dirname,
  pathApi = path,
  resourcesPath = process.resourcesPath,
} = {}) {
  const candidates = [];

  if (typeof env.CLIENT_CONFIG_FILE === "string" && env.CLIENT_CONFIG_FILE.trim()) {
    candidates.push(env.CLIENT_CONFIG_FILE.trim());
  }

  const userDataPath = appApi && typeof appApi.getPath === "function"
    ? appApi.getPath("userData")
    : "";
  if (typeof userDataPath === "string" && userDataPath.trim()) {
    candidates.push(pathApi.join(userDataPath.trim(), "client_config.json"));
  }

  if (typeof moduleDir === "string" && moduleDir.trim()) {
    candidates.push(pathApi.join(moduleDir.trim(), "build", "client_config.release.json"));
  }

  if (typeof resourcesPath === "string" && resourcesPath.trim()) {
    candidates.push(pathApi.join(resourcesPath.trim(), "client_config.json"));
    candidates.push(pathApi.join(resourcesPath.trim(), "client_config.release.json"));
  }

  return [...new Set(candidates)];
}

function readProgramAccessConfig({
  appApi = null,
  env = process.env,
  fileConfig = null,
  fsApi = fs,
  moduleDir = __dirname,
  pathApi = path,
  resourcesPath = process.resourcesPath,
} = {}) {
  const resolvedFileConfig = isPlainObject(fileConfig)
    ? fileConfig
      : resolveConfigCandidates({
        appApi,
        env,
        moduleDir,
        pathApi,
        resourcesPath,
      }).reduce((matchedConfig, candidatePath) => {
        if (Object.keys(matchedConfig).length > 0) {
          return matchedConfig;
        }
        return readJsonObject(candidatePath, fsApi);
      }, {});

  return {
    controlPlaneBaseUrl: normalizeUrl(
      env.C5_PROGRAM_CONTROL_PLANE_BASE_URL
        || env.CONTROL_PLANE_BASE_URL
        || resolvedFileConfig.controlPlaneBaseUrl
        || resolvedFileConfig.control_plane_base_url,
    ),
  };
}

module.exports = {
  readProgramAccessConfig,
};
