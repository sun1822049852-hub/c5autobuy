const assert = require("node:assert/strict");

const {readServerRuntimeOptions} = require("../src/server");

function main() {
  assert.deepEqual(readServerRuntimeOptions({}), {
    trustProxy: false
  });

  assert.deepEqual(readServerRuntimeOptions({
    PROGRAM_ADMIN_TRUST_PROXY: "true"
  }), {
    trustProxy: true
  });

  assert.deepEqual(readServerRuntimeOptions({
    TRUST_PROXY: "on"
  }), {
    trustProxy: true
  });

  assert.deepEqual(readServerRuntimeOptions({
    PROGRAM_ADMIN_TRUST_PROXY: "0",
    TRUST_PROXY: "yes"
  }), {
    trustProxy: false
  });
}

main();
