import path from "node:path";
import { createRequire } from "node:module";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const launcher = require("../../../main_ui_account_center_desktop.js");


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

  it("rebuilds the renderer when source files are newer than the existing dist bundle", () => {
    const appDirectory = "C:/demo/project/app_desktop_web";
    const distEntryPath = path.join(appDirectory, "dist", "index.html");
    const srcDirectory = path.join(appDirectory, "src");
    const featuresDirectory = path.join(srcDirectory, "features");
    const querySystemDirectory = path.join(featuresDirectory, "query-system");
    const queryPagePath = path.join(srcDirectory, "features", "query-system", "query_system_page.jsx");
    const rootIndexPath = path.join(appDirectory, "index.html");
    const viteConfigPath = path.join(appDirectory, "vite.config.js");

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
      spawnSync,
      statSync,
    });

    expect(spawnSync).toHaveBeenCalledWith(
      expect.stringMatching(/npm(?:\.cmd)?$/),
      ["--prefix", "app_desktop_web", "run", "build"],
      expect.objectContaining({
        cwd: expect.any(String),
        stdio: "inherit",
      }),
    );
  });
});
