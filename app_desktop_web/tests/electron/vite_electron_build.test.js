import { describe, expect, it } from "vitest";

import viteConfig from "../../vite.config.js";


describe("vite electron build config", () => {
  it("uses a relative asset base so Electron file:// windows can load bundled assets", () => {
    expect(viteConfig.base).toBe("./");
  });
});
