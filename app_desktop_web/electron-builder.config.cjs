const fs = require("node:fs");
const path = require("node:path");
const { resolveBundledResourcePath, resolveProjectRoots } = require("./electron-builder-paths.cjs");


function buildElectronBuilderConfig({
  appDir = __dirname,
  existsSync = fs.existsSync,
} = {}) {
  const { appDir: normalizedAppDir } = resolveProjectRoots(appDir);

  return {
    appId: "com.c5.trading-assistant",
    productName: "C5 交易助手",
    directories: {
      output: "release",
      buildResources: "build",
    },
    files: [
      "dist/**/*",
      "electron-main.cjs",
      "electron-preload.cjs",
      "electron_runtime_mode.cjs",
      "program_access_config.cjs",
      "python_backend.js",
      "renderer_diagnostics_logger.cjs",
      "window_state.js",
      "package.json",
    ],
    extraResources: [
      {
        from: path.join(normalizedAppDir, "build", "client_config.release.json"),
        to: "client_config.release.json",
      },
      {
        from: resolveBundledResourcePath({
          appDir: normalizedAppDir,
          existsSync,
          resourcePath: "app_backend",
        }),
        to: "app_backend",
        filter: [
          "**/*",
          "!**/__pycache__/**",
          "!**/.pytest_cache/**",
          "!**/*.pyc",
        ],
      },
      {
        from: resolveBundledResourcePath({
          appDir: normalizedAppDir,
          existsSync,
          resourcePath: "xsign.py",
        }),
        to: "xsign.py",
      },
      {
        from: path.join(normalizedAppDir, "build", "python_deps"),
        to: "python_deps",
        filter: [
          "**/*",
          "!**/__pycache__/**",
          "!**/.pytest_cache/**",
          "!**/*.pyc",
        ],
      },
    ],
    win: {
      target: [
        "nsis",
      ],
      // Avoid electron-builder's winCodeSign+rcedit toolchain, which requires
      // symlink privileges unavailable in the default local build environment.
      signAndEditExecutable: false,
    },
    nsis: {
      oneClick: false,
      perMachine: false,
      allowToChangeInstallationDirectory: true,
      createDesktopShortcut: "always",
      createStartMenuShortcut: true,
    },
  };
}
module.exports = buildElectronBuilderConfig();
