import { afterEach } from "vitest";

import { resetAppShellRuntimeForTests } from "../src/features/shell/app_shell_state.js";


afterEach(() => {
  if (!globalThis.window) {
    return;
  }

  try {
    globalThis.window.localStorage?.clear();
  } catch {
    // Ignore storage cleanup failures in non-jsdom tests.
  }

  try {
    globalThis.window.sessionStorage?.clear();
  } catch {
    // Ignore storage cleanup failures in non-jsdom tests.
  }

  resetAppShellRuntimeForTests();
});
