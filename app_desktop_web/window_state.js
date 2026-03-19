import fs from "node:fs";
import path from "node:path";


const DEFAULT_WINDOW_STATE = {
  width: 1440,
  height: 860,
  minWidth: 1180,
  minHeight: 760,
};


export function loadWindowState({ filePath, readText } = {}) {
  try {
    const text = readText ? readText() : fs.readFileSync(resolveStateFilePath(filePath), "utf8");
    const parsed = JSON.parse(text);
    return {
      ...DEFAULT_WINDOW_STATE,
      ...normalizeState(parsed),
    };
  } catch (_error) {
    return { ...DEFAULT_WINDOW_STATE };
  }
}


export function saveWindowState(bounds, { filePath, writeText } = {}) {
  const normalized = normalizeState(bounds);
  const text = JSON.stringify(normalized, null, 2);
  if (writeText) {
    writeText(text);
    return;
  }
  const targetPath = resolveStateFilePath(filePath);
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  fs.writeFileSync(targetPath, text, "utf8");
}


export function resolveStateFilePath(filePath) {
  return filePath || path.join(process.cwd(), ".desktop-ui", "account-center-window-state.json");
}


function normalizeState(value) {
  if (!value || typeof value !== "object") {
    return {};
  }
  return {
    x: toOptionalNumber(value.x),
    y: toOptionalNumber(value.y),
    width: toPositiveNumber(value.width),
    height: toPositiveNumber(value.height),
  };
}


function toOptionalNumber(value) {
  return Number.isFinite(Number(value)) ? Number(value) : undefined;
}


function toPositiveNumber(value) {
  return Number(value) > 0 ? Number(value) : undefined;
}
