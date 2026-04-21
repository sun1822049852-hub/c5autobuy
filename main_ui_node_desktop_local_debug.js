const path = require("node:path");

const launcher = require("./main_ui_node_desktop.js");


const LOCAL_DEBUG_CONFIG_PATH = path.join(
  __dirname,
  "app_desktop_web",
  "build",
  "client_config.local_debug.json",
);


function buildLocalDebugLaunchEnv(env = process.env) {
  return {
    ...env,
    CLIENT_CONFIG_FILE: LOCAL_DEBUG_CONFIG_PATH,
    C5_PROGRAM_ACCESS_STAGE: "prepackaging",
  };
}


function applyLocalDebugEnv(targetEnv = process.env) {
  const nextEnv = buildLocalDebugLaunchEnv(targetEnv);

  delete targetEnv.C5_PROGRAM_CONTROL_PLANE_BASE_URL;
  delete targetEnv.CONTROL_PLANE_BASE_URL;

  for (const [key, value] of Object.entries(nextEnv)) {
    targetEnv[key] = value;
  }

  return targetEnv;
}


function main() {
  applyLocalDebugEnv(process.env);
  return launcher.main();
}


if (require.main === module) {
  main();
}


module.exports = {
  LOCAL_DEBUG_CONFIG_PATH,
  applyLocalDebugEnv,
  buildLocalDebugLaunchEnv,
  main,
};
