const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");


const DEFAULT_ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/";
const RENDERER_SOURCE_RELATIVE_PATHS = [
  path.join("app_desktop_web", "src"),
  path.join("app_desktop_web", "index.html"),
  path.join("app_desktop_web", "vite.config.js"),
];


function resolveRootPath(...segments) {
  return path.join(__dirname, ...segments);
}


function resolveElectronCliScript(rootDirectory = __dirname) {
  return path.join(rootDirectory, "app_desktop_web", "node_modules", "electron", "cli.js");
}


function resolveElectronInstallScript(rootDirectory = __dirname) {
  return path.join(rootDirectory, "app_desktop_web", "node_modules", "electron", "install.js");
}


function resolveNpmCliScript() {
  try {
    return require.resolve("npm/bin/npm-cli.js");
  } catch {
    return null;
  }
}


function buildRendererBuildSpec({
  comSpec = process.env.ComSpec || "cmd.exe",
  platform = process.platform,
  resolveNpmCliScript: resolveNpmCliScriptImpl = resolveNpmCliScript,
} = {}) {
  const npmCliScript = resolveNpmCliScriptImpl();
  if (npmCliScript) {
    return {
      command: process.execPath,
      args: [
        npmCliScript,
        "--prefix",
        "app_desktop_web",
        "run",
        "build",
      ],
    };
  }

  if (platform === "win32") {
    return {
      command: comSpec,
      args: [
        "/d",
        "/s",
        "/c",
        "npm.cmd --prefix app_desktop_web run build",
      ],
    };
  }

  return {
    command: "npm",
    args: [
      "--prefix",
      "app_desktop_web",
      "run",
      "build",
    ],
  };
}


function buildElectronLaunchSpec(
  rootDirectory = __dirname,
  {
    existsSync = fs.existsSync,
    readFileSync = fs.readFileSync,
  } = {},
) {
  const runtimeExecutablePath = resolveElectronRuntimeExecutablePath(rootDirectory, {
    existsSync,
    readFileSync,
  });

  if (runtimeExecutablePath && existsSync(runtimeExecutablePath)) {
    return {
      command: runtimeExecutablePath,
      args: [
        path.join(rootDirectory, "app_desktop_web"),
      ],
    };
  }

  return {
    command: process.execPath,
    args: [
      resolveElectronCliScript(rootDirectory),
      path.join(rootDirectory, "app_desktop_web"),
    ],
  };
}


function buildElectronLaunchEnv(env = process.env, { nowMs = Date.now() } = {}) {
  const launchEnv = Object.fromEntries(
    Object.entries(env).filter(([key]) => key.toUpperCase() !== "ELECTRON_RUN_AS_NODE"),
  );

  if (
    String(launchEnv.C5_STARTUP_TRACE || "").trim() === "1"
    && !String(launchEnv.C5_STARTUP_TRACE_ORIGIN_MS || "").trim()
  ) {
    launchEnv.C5_STARTUP_TRACE_ORIGIN_MS = String(nowMs);
  }

  return launchEnv;
}


function resolveElectronRuntimeExecutablePath(
  rootDirectory = __dirname,
  {
    existsSync = fs.existsSync,
    readFileSync = fs.readFileSync,
  } = {},
) {
  const electronDirectory = path.join(rootDirectory, "app_desktop_web", "node_modules", "electron");
  const pathFile = path.join(electronDirectory, "path.txt");

  if (!existsSync(pathFile)) {
    return null;
  }

  let executableRelativePath = "";
  try {
    executableRelativePath = readFileSync(pathFile, "utf-8").trim();
  } catch {
    return null;
  }

  if (!executableRelativePath) {
    return null;
  }

  return path.join(electronDirectory, "dist", executableRelativePath);
}


function isElectronRuntimeInstalled(
  rootDirectory = __dirname,
  {
    existsSync = fs.existsSync,
    readFileSync = fs.readFileSync,
  } = {},
) {
  const executablePath = resolveElectronRuntimeExecutablePath(rootDirectory, {
    existsSync,
    readFileSync,
  });

  return executablePath !== null && existsSync(executablePath);
}


function buildElectronInstallEnv(env = process.env) {
  if (
    env.ELECTRON_MIRROR ||
    env.npm_config_electron_mirror ||
    env.NPM_CONFIG_ELECTRON_MIRROR ||
    env.npm_package_config_electron_mirror
  ) {
    return env;
  }

  return {
    ...env,
    ELECTRON_MIRROR: DEFAULT_ELECTRON_MIRROR,
  };
}


function ensureElectronRuntime(
  rootDirectory = __dirname,
  {
    env = process.env,
    existsSync = fs.existsSync,
    readFileSync = fs.readFileSync,
    spawnSync: spawnSyncImpl = spawnSync,
  } = {},
) {
  if (isElectronRuntimeInstalled(rootDirectory, { existsSync, readFileSync })) {
    return;
  }

  const installScript = resolveElectronInstallScript(rootDirectory);

  if (!existsSync(installScript)) {
    throw new Error("未找到 Electron 安装脚本，请先执行 npm --prefix app_desktop_web install");
  }

  const installResult = spawnSyncImpl(process.execPath, [installScript], {
    cwd: rootDirectory,
    env: buildElectronInstallEnv(env),
    stdio: "inherit",
    windowsHide: false,
  });

  if (installResult.error) {
    throw installResult.error;
  }

  if (installResult.status !== 0) {
    throw new Error("Electron 运行时自动修复失败，请执行 npm --prefix app_desktop_web install");
  }

  if (!isElectronRuntimeInstalled(rootDirectory, { existsSync, readFileSync })) {
    throw new Error("Electron 运行时仍未安装完整，请执行 npm --prefix app_desktop_web install");
  }
}

function getLatestModifiedTimeMs(
  targetPath,
  {
    existsSync = fs.existsSync,
    readdirSync = fs.readdirSync,
    statSync = fs.statSync,
  } = {},
) {
  if (!existsSync(targetPath)) {
    return 0;
  }

  const stat = statSync(targetPath);
  if (!stat.isDirectory()) {
    return stat.mtimeMs;
  }

  return readdirSync(targetPath).reduce((latestTime, entryName) => {
    const entryPath = path.join(targetPath, entryName);
    return Math.max(latestTime, getLatestModifiedTimeMs(entryPath, {
      existsSync,
      readdirSync,
      statSync,
    }));
  }, stat.mtimeMs);
}


function normalizeGitPath(targetPath) {
  return targetPath.split(path.sep).join("/");
}


function runGitCommand(
  args,
  {
    cwd = __dirname,
    spawnSync: spawnSyncImpl = spawnSync,
  } = {},
) {
  const result = spawnSyncImpl("git", args, {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  if (result.error || result.status !== 0) {
    return null;
  }

  return typeof result.stdout === "string" ? result.stdout : null;
}


function getRendererBuildDecisionFromGit(
  appDirectory,
  {
    existsSync = fs.existsSync,
    runGitCommand: runGitCommandImpl = runGitCommand,
    statSync = fs.statSync,
  } = {},
) {
  const workspaceRoot = path.dirname(appDirectory);
  const distEntryPath = path.join(appDirectory, "dist", "index.html");
  const gitSourcePaths = RENDERER_SOURCE_RELATIVE_PATHS.map((relativePath) => (
    normalizeGitPath(relativePath)
  ));
  const statusOutput = runGitCommandImpl([
    "status",
    "--porcelain",
    "--untracked-files=all",
    "--no-renames",
    "--",
    ...gitSourcePaths,
  ], {
    cwd: workspaceRoot,
  });

  if (statusOutput === null) {
    return null;
  }

  const latestCommitOutput = runGitCommandImpl([
    "log",
    "-1",
    "--format=%ct",
    "--",
    ...gitSourcePaths,
  ], {
    cwd: workspaceRoot,
  });

  const distMtimeMs = statSync(distEntryPath).mtimeMs;
  let latestRendererChangeMs = 0;
  if (latestCommitOutput !== null) {
    const latestCommitSeconds = Number.parseInt(latestCommitOutput.trim(), 10);
    if (Number.isFinite(latestCommitSeconds)) {
      latestRendererChangeMs = latestCommitSeconds * 1000;
    }
  }

  const statusLines = statusOutput
    .split(/\r?\n/u)
    .map((line) => line.trimEnd())
    .filter(Boolean);

  for (const statusLine of statusLines) {
    const indexStatus = statusLine[0] ?? " ";
    const worktreeStatus = statusLine[1] ?? " ";
    const relativePath = statusLine.slice(3);

    if (
      ["D", "T", "U"].includes(indexStatus)
      || ["D", "T", "U"].includes(worktreeStatus)
      || !relativePath
    ) {
      return {
        shouldBuild: true,
        strategy: "git",
      };
    }

    const absolutePath = path.join(workspaceRoot, ...relativePath.split("/"));
    if (!existsSync(absolutePath)) {
      return {
        shouldBuild: true,
        strategy: "git",
      };
    }

    latestRendererChangeMs = Math.max(
      latestRendererChangeMs,
      statSync(absolutePath).mtimeMs,
    );
  }

  return {
    shouldBuild: latestRendererChangeMs > distMtimeMs,
    strategy: "git",
  };
}


function ensureRendererBuild(
  appDirectory,
  {
    env = process.env,
    existsSync = fs.existsSync,
    readdirSync = fs.readdirSync,
    runGitCommand: runGitCommandImpl = runGitCommand,
    resolveNpmCliScript: resolveNpmCliScriptImpl = resolveNpmCliScript,
    spawnSync: spawnSyncImpl = spawnSync,
    statSync = fs.statSync,
    platform = process.platform,
    comSpec = process.env.ComSpec || "cmd.exe",
  } = {},
) {
  const distEntryPath = path.join(appDirectory, "dist", "index.html");
  const sourcePaths = [
    path.join(appDirectory, "src"),
    path.join(appDirectory, "index.html"),
    path.join(appDirectory, "vite.config.js"),
  ];
  const reuseExistingDist = String(env.C5_LOCAL_DEBUG_REUSE_RENDERER_DIST || "").trim() === "1";
  const hasBuiltDist = existsSync(distEntryPath);
  if (reuseExistingDist && hasBuiltDist) {
    return;
  }

  let shouldBuild = !hasBuiltDist;
  if (!shouldBuild) {
    const gitDecision = getRendererBuildDecisionFromGit(appDirectory, {
      existsSync,
      runGitCommand: runGitCommandImpl,
      statSync,
    });
    if (gitDecision) {
      shouldBuild = gitDecision.shouldBuild;
    } else {
      const distMtimeMs = getLatestModifiedTimeMs(distEntryPath, {
        existsSync,
        readdirSync,
        statSync,
      });
      shouldBuild = sourcePaths.some((sourcePath) => (
        getLatestModifiedTimeMs(sourcePath, {
          existsSync,
          readdirSync,
          statSync,
        }) > distMtimeMs
      ));
    }
  }

  if (!shouldBuild) {
    return;
  }

  const buildSpec = buildRendererBuildSpec({
    comSpec,
    platform,
    resolveNpmCliScript: resolveNpmCliScriptImpl,
  });
  const buildResult = spawnSyncImpl(
    buildSpec.command,
    buildSpec.args,
    {
      cwd: __dirname,
      stdio: "inherit",
    },
  );

  if (buildResult.error) {
    throw buildResult.error;
  }

  if (buildResult.status !== 0) {
    process.exit(buildResult.status ?? 1);
  }
}


function main() {
  const appDirectory = resolveRootPath("app_desktop_web");
  const electronExecutablePath = resolveElectronRuntimeExecutablePath();
  const electronCliScript = resolveElectronCliScript();

  if (!electronExecutablePath && !fs.existsSync(electronCliScript)) {
    console.error("未找到 Electron 可执行文件，请先执行 npm --prefix app_desktop_web install");
    process.exit(1);
  }

  ensureRendererBuild(appDirectory);
  ensureElectronRuntime(__dirname);

  const launchSpec = buildElectronLaunchSpec(__dirname);
  const child = spawn(launchSpec.command, launchSpec.args, {
    cwd: __dirname,
    env: buildElectronLaunchEnv(process.env),
    stdio: "inherit",
    windowsHide: false,
  });

  child.on("exit", (code) => {
    process.exit(code ?? 0);
  });
}


if (require.main === module) {
  main();
}


module.exports = {
  buildElectronLaunchEnv,
  buildElectronLaunchSpec,
  buildRendererBuildSpec,
  buildElectronInstallEnv,
  ensureElectronRuntime,
  ensureRendererBuild,
  getLatestModifiedTimeMs,
  isElectronRuntimeInstalled,
  main,
  resolveElectronCliScript,
  resolveElectronInstallScript,
  resolveNpmCliScript,
  runGitCommand,
};
