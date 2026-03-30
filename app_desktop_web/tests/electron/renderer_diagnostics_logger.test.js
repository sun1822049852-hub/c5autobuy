import path from "node:path";
import { createRequire } from "node:module";

import { describe, expect, it, vi } from "vitest";


const require = createRequire(import.meta.url);
const logger = require("../../renderer_diagnostics_logger.cjs");


describe("renderer diagnostics logger", () => {
  it("writes normalized diagnostic events into the Electron user data directory", () => {
    const appendFileSync = vi.fn();
    const mkdirSync = vi.fn();
    const logPath = logger.appendRendererDiagnostic({
      type: "renderer_window_error",
      details: {
        message: "renderer exploded",
      },
    }, {
      appApi: {
        getPath(target) {
          expect(target).toBe("userData");
          return "C:/demo/user-data";
        },
      },
      appendFileSync,
      mkdirSync,
      now: () => "2026-03-30T09:00:00.000Z",
    });

    expect(logPath).toBe(path.join("C:/demo/user-data", "renderer-diagnostics.jsonl"));
    expect(mkdirSync).toHaveBeenCalledWith(path.join("C:/demo", "user-data"), { recursive: true });
    expect(appendFileSync).toHaveBeenCalledTimes(1);

    const [writtenPath, writtenPayload, encoding] = appendFileSync.mock.calls[0];
    expect(writtenPath).toBe(path.join("C:/demo/user-data", "renderer-diagnostics.jsonl"));
    expect(encoding).toBe("utf8");
    expect(JSON.parse(writtenPayload)).toEqual({
      timestamp: "2026-03-30T09:00:00.000Z",
      type: "renderer_window_error",
      href: null,
      details: {
        message: "renderer exploded",
      },
    });
  });

  it("falls back to safe primitive values when the renderer payload is not an object", () => {
    const appendFileSync = vi.fn();

    logger.appendRendererDiagnostic("plain text failure", {
      appApi: {
        getPath() {
          return "C:/demo/user-data";
        },
      },
      appendFileSync,
      mkdirSync: vi.fn(),
      now: () => "2026-03-30T09:10:00.000Z",
    });

    const [, writtenPayload] = appendFileSync.mock.calls[0];
    expect(JSON.parse(writtenPayload)).toEqual({
      timestamp: "2026-03-30T09:10:00.000Z",
      type: "renderer-diagnostic",
      href: null,
      details: {
        value: "plain text failure",
      },
    });
  });
});
