import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";


describe("index startup shell", () => {
  it("ships a static startup shell inside the root container before React mounts", () => {
    const indexHtmlPath = path.resolve(process.cwd(), "index.html");
    const html = fs.readFileSync(indexHtmlPath, "utf8");

    expect(html).toContain('<div id="root">');
    expect(html).toContain('app-static-startup-shell');
    expect(html).toContain("主界面启动中");
    expect(html).toContain("正在准备界面与本地服务");
  });
});
