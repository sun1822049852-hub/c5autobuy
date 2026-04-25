import path from "node:path";
import { createRequire } from "node:module";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const launcher = require("../../../main_ui_node_desktop.js");


describe("desktop launcher", () => {
  it("builds a direct electron runtime launch command when the runtime payload is installed", () => {
    const rootDir = "C:/demo/project";
    const pathFile = path.join(rootDir, "app_desktop_web", "node_modules", "electron", "path.txt");
    const electronExe = path.join(rootDir, "app_desktop_web", "node_modules", "electron", "dist", "electron.exe");

    const spec = launcher.buildElectronLaunchSpec(rootDir, {
      existsSync: (targetPath) => targetPath === pathFile || targetPath === electronExe,
      readFileSync: () => "electron.exe",
    });

    expect(spec.command).toBe(electronExe);
    expect(spec.args).toEqual([
      path.join(rootDir, "app_desktop_web"),
    ]);
  });

  it("falls back to the node-driven electron cli launch command when the runtime payload is unavailable", () => {
    const rootDir = "C:/demo/project";

    const spec = launcher.buildElectronLaunchSpec(rootDir, {
      existsSync: () => false,
      readFileSync: () => {
        throw new Error("missing runtime");
      },
    });

    expect(spec.command).toBe(process.execPath);
    expect(spec.args).toEqual([
      path.join(rootDir, "app_desktop_web", "node_modules", "electron", "cli.js"),
      path.join(rootDir, "app_desktop_web"),
    ]);
  });

  it("strips ELECTRON_RUN_AS_NODE before launching the desktop app", () => {
    const env = launcher.buildElectronLaunchEnv({
      ELECTRON_RUN_AS_NODE: "1",
      PATH: "C:/Windows/System32",
      USERPROFILE: "C:/Users/demo",
    });

    expect(env).toEqual({
      PATH: "C:/Windows/System32",
      USERPROFILE: "C:/Users/demo",
    });
    expect("ELECTRON_RUN_AS_NODE" in env).toBe(false);
  });

  it("propagates a shared startup trace origin when tracing the real desktop launch", () => {
    const env = launcher.buildElectronLaunchEnv({
      C5_STARTUP_TRACE: "1",
      ELECTRON_RUN_AS_NODE: "1",
      PATH: "C:/Windows/System32",
      USERPROFILE: "C:/Users/demo",
    }, {
      nowMs: 1735689600123,
    });

    expect(env).toEqual({
      C5_STARTUP_TRACE: "1",
      C5_STARTUP_TRACE_ORIGIN_MS: "1735689600123",
      PATH: "C:/Windows/System32",
      USERPROFILE: "C:/Users/demo",
    });
    expect("ELECTRON_RUN_AS_NODE" in env).toBe(false);
  });

  it("repairs a broken electron runtime before launch when the package payload is missing", () => {
    const rootDir = "C:/demo/project";
    const electronDir = path.join(rootDir, "app_desktop_web", "node_modules", "electron");
    const cliScript = path.join(electronDir, "cli.js");
    const installScript = path.join(electronDir, "install.js");
    const pathFile = path.join(electronDir, "path.txt");
    const runtimeExe = path.join(electronDir, "dist", "electron.exe");
    let runtimeInstalled = false;

    const existsSync = vi.fn((targetPath) => {
      if (targetPath === cliScript || targetPath === installScript) {
        return true;
      }
      if (targetPath === pathFile || targetPath === runtimeExe) {
        return runtimeInstalled;
      }
      return false;
    });
    const readFileSync = vi.fn((targetPath) => {
      if (targetPath === pathFile && runtimeInstalled) {
        return "electron.exe";
      }
      throw new Error(`missing: ${targetPath}`);
    });
    const env = {
      PATH: "C:/Windows/System32",
    };
    const spawnSync = vi.fn(() => {
      runtimeInstalled = true;
      return { status: 0 };
    });

    launcher.ensureElectronRuntime(rootDir, {
      env,
      existsSync,
      readFileSync,
      spawnSync,
    });

    expect(spawnSync).toHaveBeenCalledWith(
      process.execPath,
      [installScript],
      expect.objectContaining({
        cwd: rootDir,
        env: expect.objectContaining({
          ELECTRON_MIRROR: "https://npmmirror.com/mirrors/electron/",
          PATH: "C:/Windows/System32",
        }),
        stdio: "inherit",
      }),
    );
  });

  it("does not require electron cli.js when the runtime executable is already installed", () => {
    const rootDir = "C:/demo/project";
    const electronDir = path.join(rootDir, "app_desktop_web", "node_modules", "electron");
    const installScript = path.join(electronDir, "install.js");
    const pathFile = path.join(electronDir, "path.txt");
    const runtimeExe = path.join(electronDir, "dist", "electron.exe");
    const spawnSync = vi.fn();

    launcher.ensureElectronRuntime(rootDir, {
      existsSync: (targetPath) => (
        targetPath === installScript
        || targetPath === pathFile
        || targetPath === runtimeExe
      ),
      readFileSync: (targetPath) => {
        if (targetPath === pathFile) {
          return "electron.exe";
        }
        throw new Error(`unexpected path read: ${targetPath}`);
      },
      spawnSync,
    });

    expect(spawnSync).not.toHaveBeenCalled();
  });

  it("rebuilds the renderer through node plus npm cli to avoid windows npm.cmd spawn errors", () => {
    const appDirectory = "C:/demo/project/app_desktop_web";
    const distEntryPath = path.join(appDirectory, "dist", "index.html");
    const srcDirectory = path.join(appDirectory, "src");
    const featuresDirectory = path.join(srcDirectory, "features");
    const querySystemDirectory = path.join(featuresDirectory, "query-system");
    const queryPagePath = path.join(srcDirectory, "features", "query-system", "query_system_page.jsx");
    const rootIndexPath = path.join(appDirectory, "index.html");
    const viteConfigPath = path.join(appDirectory, "vite.config.js");
    const npmCliPath = "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js";

    const existingPaths = new Set([
      distEntryPath,
      srcDirectory,
      featuresDirectory,
      querySystemDirectory,
      queryPagePath,
      rootIndexPath,
      viteConfigPath,
    ]);

    const existsSync = vi.fn((targetPath) => existingPaths.has(targetPath));
    const statSync = vi.fn((targetPath) => {
      if (targetPath === distEntryPath) {
        return { isDirectory: () => false, mtimeMs: 100 };
      }
      if (targetPath === srcDirectory) {
        return { isDirectory: () => true, mtimeMs: 0 };
      }
      if (targetPath === featuresDirectory || targetPath === querySystemDirectory) {
        return { isDirectory: () => true, mtimeMs: 0 };
      }
      if (targetPath === queryPagePath) {
        return { isDirectory: () => false, mtimeMs: 200 };
      }
      if (targetPath === rootIndexPath || targetPath === viteConfigPath) {
        return { isDirectory: () => false, mtimeMs: 90 };
      }
      throw new Error(`unexpected path: ${targetPath}`);
    });
    const readdirSync = vi.fn((targetPath) => {
      if (targetPath === srcDirectory) {
        return ["features"];
      }
      if (targetPath === path.join(srcDirectory, "features")) {
        return ["query-system"];
      }
      if (targetPath === path.join(srcDirectory, "features", "query-system")) {
        return ["query_system_page.jsx"];
      }
      return [];
    });
    const spawnSync = vi.fn(() => ({ status: 0 }));

    launcher.ensureRendererBuild(appDirectory, {
      existsSync,
      readdirSync,
      resolveNpmCliScript: () => npmCliPath,
      spawnSync,
      statSync,
      platform: "win32",
    });

    expect(spawnSync).toHaveBeenCalledWith(
      process.execPath,
      [npmCliPath, "--prefix", "app_desktop_web", "run", "build"],
      expect.objectContaining({
        cwd: expect.any(String),
        stdio: "inherit",
      }),
    );
  });

  it("skips recursive source scanning when git can already prove the existing dist is current", () => {
    const appDirectory = "C:/demo/project/app_desktop_web";
    const distEntryPath = path.join(appDirectory, "dist", "index.html");
    const appPath = path.join(appDirectory, "src", "App.jsx");
    const existsSync = vi.fn((targetPath) => (
      targetPath === distEntryPath
      || targetPath === appPath
    ));
    const statSync = vi.fn((targetPath) => {
      if (targetPath === distEntryPath) {
        return { isDirectory: () => false, mtimeMs: 400 };
      }
      if (targetPath === appPath) {
        return { isDirectory: () => false, mtimeMs: 350 };
      }
      throw new Error(`unexpected path: ${targetPath}`);
    });
    const readdirSync = vi.fn(() => {
      throw new Error("should not scan renderer source tree");
    });
    const runGitCommand = vi.fn((args) => {
      if (args[0] === "status") {
        return " M app_desktop_web/src/App.jsx\n";
      }
      if (args[0] === "log") {
        return "0\n";
      }
      throw new Error(`unexpected git args: ${args.join(" ")}`);
    });
    const spawnSync = vi.fn(() => ({ status: 0 }));

    launcher.ensureRendererBuild(appDirectory, {
      existsSync,
      readdirSync,
      runGitCommand,
      spawnSync,
      statSync,
      platform: "win32",
    });

    expect(runGitCommand).toHaveBeenCalledTimes(2);
    expect(spawnSync).not.toHaveBeenCalled();
  });

  it("still rebuilds when git reports a renderer file newer than the current dist", () => {
    const appDirectory = "C:/demo/project/app_desktop_web";
    const distEntryPath = path.join(appDirectory, "dist", "index.html");
    const appPath = path.join(appDirectory, "src", "App.jsx");
    const npmCliPath = "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js";
    const existsSync = vi.fn((targetPath) => (
      targetPath === distEntryPath
      || targetPath === appPath
    ));
    const statSync = vi.fn((targetPath) => {
      if (targetPath === distEntryPath) {
        return { isDirectory: () => false, mtimeMs: 100 };
      }
      if (targetPath === appPath) {
        return { isDirectory: () => false, mtimeMs: 250 };
      }
      throw new Error(`unexpected path: ${targetPath}`);
    });
    const readdirSync = vi.fn(() => {
      throw new Error("should not scan renderer source tree");
    });
    const runGitCommand = vi.fn((args) => {
      if (args[0] === "status") {
        return " M app_desktop_web/src/App.jsx\n";
      }
      if (args[0] === "log") {
        return "0\n";
      }
      throw new Error(`unexpected git args: ${args.join(" ")}`);
    });
    const spawnSync = vi.fn(() => ({ status: 0 }));

    launcher.ensureRendererBuild(appDirectory, {
      existsSync,
      readdirSync,
      resolveNpmCliScript: () => npmCliPath,
      runGitCommand,
      spawnSync,
      statSync,
      platform: "win32",
    });

    expect(spawnSync).toHaveBeenCalledWith(
      process.execPath,
      [npmCliPath, "--prefix", "app_desktop_web", "run", "build"],
      expect.objectContaining({
        cwd: expect.any(String),
        stdio: "inherit",
      }),
    );
  });

  it("provides an explicit local debug launcher that forces prepackaging mode", () => {
    const localDebugLauncher = require("../../../main_ui_node_desktop_local_debug.js");
    const env = localDebugLauncher.buildLocalDebugLaunchEnv({
      PATH: "C:/Windows/System32",
    });

    expect(env).toEqual(expect.objectContaining({
      PATH: "C:/Windows/System32",
      C5_PROGRAM_ACCESS_STAGE: "prepackaging",
      CLIENT_CONFIG_FILE: expect.stringMatching(/client_config\.local_debug\.json$/),
      C5_LOCAL_DEBUG_REUSE_RENDERER_DIST: "1",
    }));
  });

  it("reuses the existing renderer dist for local debug even when source files are newer", () => {
    const appDirectory = "C:/demo/project/app_desktop_web";
    const distEntryPath = path.join(appDirectory, "dist", "index.html");
    const srcDirectory = path.join(appDirectory, "src");
    const featuresDirectory = path.join(srcDirectory, "features");
    const querySystemDirectory = path.join(featuresDirectory, "query-system");
    const queryPagePath = path.join(srcDirectory, "features", "query-system", "query_system_page.jsx");
    const rootIndexPath = path.join(appDirectory, "index.html");
    const viteConfigPath = path.join(appDirectory, "vite.config.js");
    const npmCliPath = "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js";

    const existingPaths = new Set([
      distEntryPath,
      srcDirectory,
      featuresDirectory,
      querySystemDirectory,
      queryPagePath,
      rootIndexPath,
      viteConfigPath,
    ]);

    const existsSync = vi.fn((targetPath) => existingPaths.has(targetPath));
    const statSync = vi.fn((targetPath) => {
      if (targetPath === distEntryPath) {
        return { isDirectory: () => false, mtimeMs: 100 };
      }
      if (targetPath === srcDirectory) {
        return { isDirectory: () => true, mtimeMs: 0 };
      }
      if (targetPath === featuresDirectory || targetPath === querySystemDirectory) {
        return { isDirectory: () => true, mtimeMs: 0 };
      }
      if (targetPath === queryPagePath) {
        return { isDirectory: () => false, mtimeMs: 200 };
      }
      if (targetPath === rootIndexPath || targetPath === viteConfigPath) {
        return { isDirectory: () => false, mtimeMs: 90 };
      }
      throw new Error(`unexpected path: ${targetPath}`);
    });
    const readdirSync = vi.fn((targetPath) => {
      if (targetPath === srcDirectory) {
        return ["features"];
      }
      if (targetPath === path.join(srcDirectory, "features")) {
        return ["query-system"];
      }
      if (targetPath === path.join(srcDirectory, "features", "query-system")) {
        return ["query_system_page.jsx"];
      }
      return [];
    });
    const spawnSync = vi.fn(() => ({ status: 0 }));

    launcher.ensureRendererBuild(appDirectory, {
      env: {
        C5_LOCAL_DEBUG_REUSE_RENDERER_DIST: "1",
      },
      existsSync,
      readdirSync,
      resolveNpmCliScript: () => npmCliPath,
      spawnSync,
      statSync,
      platform: "win32",
    });

    expect(spawnSync).not.toHaveBeenCalled();
  });
});
