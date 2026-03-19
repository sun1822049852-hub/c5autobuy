import { createRequire } from "node:module";


const require = createRequire(import.meta.url);


export function loadElectronMainApis(requireImpl = require) {
  try {
    return requireImpl("electron/main");
  } catch (error) {
    if (error?.code !== "MODULE_NOT_FOUND" && error?.code !== "ERR_MODULE_NOT_FOUND") {
      throw error;
    }

    return requireImpl("electron");
  }
}
