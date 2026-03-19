import { describe, expect, it, vi } from "vitest";

import { loadElectronMainApis } from "../../electron_runtime.js";


describe("electron runtime loader", () => {
  it("loads main-process Electron APIs through CommonJS require", () => {
    const apis = {
      BrowserWindow: class {},
      app: {},
      ipcMain: {},
    };
    const requireImpl = vi.fn(() => apis);

    const result = loadElectronMainApis(requireImpl);

    expect(result).toBe(apis);
    expect(requireImpl).toHaveBeenCalledWith("electron/main");
  });

  it("falls back to the electron package when electron/main is unavailable", () => {
    const apis = {
      BrowserWindow: class {},
      app: {},
      ipcMain: {},
    };
    const requireImpl = vi
      .fn()
      .mockImplementationOnce(() => {
        const error = new Error("missing");
        error.code = "MODULE_NOT_FOUND";
        throw error;
      })
      .mockImplementationOnce(() => apis);

    const result = loadElectronMainApis(requireImpl);

    expect(result).toBe(apis);
    expect(requireImpl).toHaveBeenNthCalledWith(1, "electron/main");
    expect(requireImpl).toHaveBeenNthCalledWith(2, "electron");
  });
});
