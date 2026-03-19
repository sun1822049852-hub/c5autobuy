import { describe, expect, it } from "vitest";

import { loadWindowState, saveWindowState } from "../../window_state.js";


describe("window state store", () => {
  it("returns default bounds when state file does not exist", () => {
    const result = loadWindowState({
      readText: () => {
        throw new Error("missing");
      },
    });

    expect(result).toEqual({
      width: 1440,
      height: 860,
      minWidth: 1180,
      minHeight: 760,
    });
  });

  it("saves and restores window bounds", () => {
    let writtenText = "";

    saveWindowState(
      {
        x: 120,
        y: 80,
        width: 1480,
        height: 920,
      },
      {
        writeText: (text) => {
          writtenText = text;
        },
      },
    );

    const restored = loadWindowState({
      readText: () => writtenText,
    });

    expect(restored).toEqual({
      x: 120,
      y: 80,
      width: 1480,
      height: 920,
      minWidth: 1180,
      minHeight: 760,
    });
  });
});
