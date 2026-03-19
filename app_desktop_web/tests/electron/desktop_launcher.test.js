import path from "node:path";
import { createRequire } from "node:module";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const launcher = require("../../../main_ui_account_center_desktop.js");


describe("desktop launcher", () => {
  it("builds a node-driven electron launch command instead of spawning electron.cmd directly", () => {
    const rootDir = "C:/demo/project";

    const spec = launcher.buildElectronLaunchSpec(rootDir);

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
});
