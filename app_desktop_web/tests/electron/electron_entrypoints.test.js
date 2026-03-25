import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";


describe("electron entrypoints", () => {
  it("uses CommonJS files for the main and preload entrypoints", () => {
    const packageJsonPath = path.join(process.cwd(), "package.json");
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
    const mainEntryPath = path.join(process.cwd(), packageJson.main);
    const legacyMainEntryPath = path.join(process.cwd(), "electron-main.js");
    const preloadEntryPath = path.join(process.cwd(), "electron-preload.cjs");
    const mainEntrySource = fs.readFileSync(mainEntryPath, "utf8");
    const preloadEntrySource = fs.readFileSync(preloadEntryPath, "utf8");

    expect(packageJson.main).toBe("electron-main.cjs");
    expect(fs.existsSync(legacyMainEntryPath)).toBe(false);
    expect(mainEntrySource).toContain("electron-preload.cjs");
    expect(mainEntrySource).toContain("require(\"electron\")");
    expect(preloadEntrySource).toContain("require(\"electron\")");
  });
});
