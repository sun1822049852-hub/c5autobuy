#!/usr/bin/env node
const path = require("node:path");
const {ControlPlaneStore} = require(path.join(__dirname, "..", "src", "controlPlaneStore"));
const {PATHS} = require(path.join(__dirname, "..", "src", "constants"));

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function readArg(names = [], fallback = "") {
  for (const name of names) {
    const index = process.argv.indexOf(name);
    if (index >= 0 && index + 1 < process.argv.length) {
      const value = toText(process.argv[index + 1]);
      if (value) {
        return value;
      }
    }
  }
  return fallback;
}

function usage() {
  console.error(
    "Usage: node tools/initProgramControlPlaneAdmin.js --password \"YourPassword\" [--username admin] [--db-path path]"
  );
}

function main() {
  const username = readArg(["--username"], "admin") || "admin";
  const password = readArg(["--password"], "");
  const dbPath = readArg(["--db-path", "--db"], PATHS.DEFAULT_DB_FILE) || PATHS.DEFAULT_DB_FILE;

  if (!password) {
    usage();
    process.exit(1);
  }

  const store = new ControlPlaneStore({dbPath});
  try {
    const user = store.createOrUpdateAdminUser({
      username,
      password,
      isSuperAdmin: true
    });
    console.log(`control-plane admin ready: ${user.username} (${path.resolve(dbPath)})`);
  } finally {
    store.close();
  }
}

if (require.main === module) {
  main();
}

