const fs = require("node:fs");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");


const DEFAULT_ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/";


function resolveRootPath(...segments) {
  return path.join(__dirname, ...segments);
}


function resolveElectronCliScript(rootDirectory = __dirname) {
  return path.join(rootDirectory, "app_desktop_web", "node_modules", "electron", "cli.js");
}


function resolveElectronInstallScript(rootDirectory = __dirname) {
  return path.join(rootDirectory, "app_desktop_web", "node_modules", "electron", "install.js");
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


function buildElectronLaunchEnv(env = process.env) {
  return Object.fromEntries(
    Object.entries(env).filter(([key]) => key.toUpperCase() !== "ELECTRON_RUN_AS_NODE"),
  );
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
  const cliScript = resolveElectronCliScript(rootDirectory);
  const installScript = resolveElectronInstallScript(rootDirectory);

  if (!existsSync(cliScript) || !existsSync(installScript)) {
    throw new Error("未找到 Electron 安装脚本，请先执行 npm --prefix app_desktop_web install");
  }

  if (isElectronRuntimeInstalled(rootDirectory, { existsSync, readFileSync })) {
    return;
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


function ensureRendererBuild(
  appDirectory,
  {
    existsSync = fs.existsSync,
    readdirSync = fs.readdirSync,
    spawnSync: spawnSyncImpl = spawnSync,
    statSync = fs.statSync,
  } = {},
) {
  const distEntryPath = path.join(appDirectory, "dist", "index.html");
  const sourcePaths = [
    path.join(appDirectory, "src"),
    path.join(appDirectory, "index.html"),
    path.join(appDirectory, "vite.config.js"),
  ];

  const shouldBuild = !existsSync(distEntryPath) || sourcePaths.some((sourcePath) => (
    getLatestModifiedTimeMs(sourcePath, {
      existsSync,
      readdirSync,
      statSync,
    }) > getLatestModifiedTimeMs(distEntryPath, {
      existsSync,
      readdirSync,
      statSync,
    })
  ));

  if (!shouldBuild) {
    return;
  }

  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  const buildResult = spawnSyncImpl(
    npmCommand,
    ["--prefix", "app_desktop_web", "run", "build"],
    {
      cwd: __dirname,
      stdio: "inherit",
    },
  );

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
  buildElectronInstallEnv,
  ensureElectronRuntime,
  ensureRendererBuild,
  getLatestModifiedTimeMs,
  isElectronRuntimeInstalled,
  main,
  resolveElectronCliScript,
  resolveElectronInstallScript,
};
