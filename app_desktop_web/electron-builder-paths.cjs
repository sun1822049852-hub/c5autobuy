const fs = require("node:fs");
const path = require("node:path");


function resolveProjectRoots(appDir) {
  const normalizedAppDir = path.resolve(appDir);
  const workspaceRoot = path.resolve(normalizedAppDir, "..");
  const workspaceParent = path.dirname(workspaceRoot);
  const repoRoot = path.basename(workspaceParent) === ".worktrees"
    ? path.resolve(workspaceRoot, "..", "..")
    : workspaceRoot;

  return {
    appDir: normalizedAppDir,
    repoRoot,
    workspaceRoot,
  };
}


function resolveBundledResourcePath({
  appDir,
  existsSync = fs.existsSync,
  resourcePath,
}) {
  if (typeof resourcePath !== "string" || resourcePath.trim() === "") {
    throw new Error("resourcePath is required");
  }

  const { repoRoot, workspaceRoot } = resolveProjectRoots(appDir);
  const candidates = [
    path.resolve(workspaceRoot, resourcePath),
    path.resolve(repoRoot, resourcePath),
  ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return candidates[candidates.length - 1];
}


module.exports = {
  resolveBundledResourcePath,
  resolveProjectRoots,
};
