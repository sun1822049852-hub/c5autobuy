const path = require("node:path");

const PATHS = Object.freeze({
  DEFAULT_DB_FILE: path.resolve(__dirname, "../data/control-plane.sqlite"),
  DEFAULT_PRIVATE_KEY_FILE: path.resolve(__dirname, "../keys/entitlement-private.pem")
});

const DEFAULTS = Object.freeze({
  SNAPSHOT_TTL_MINUTES: 30,
  RUNTIME_PERMIT_TTL_SECONDS: 120
});

const MEMBERSHIP_PLANS = Object.freeze([
  {code: "inactive", permissions: []},
  {code: "member", permissions: ["program_access_enabled", "runtime.start"]}
]);

const PERMISSION_CODES = Object.freeze([
  "program_access_enabled",
  "runtime.start",
  "account.browser_query.enable"
]);

const RUNTIME_PERMIT_ACTIONS = Object.freeze([
  "runtime.start"
]);

module.exports = {
  PATHS,
  DEFAULTS,
  MEMBERSHIP_PLANS,
  PERMISSION_CODES,
  RUNTIME_PERMIT_ACTIONS
};
