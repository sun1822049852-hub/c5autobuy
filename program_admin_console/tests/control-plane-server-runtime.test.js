const assert = require("node:assert/strict");

const {readServerRuntimeOptions, getSourceIp} = require("../src/server");

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

  assert.equal(
    getSourceIp({
      headers: {"x-forwarded-for": "127.0.0.1, 10.0.0.1"},
      socket: {remoteAddress: "203.0.113.10"}
    }, {trustProxy: true}),
    "203.0.113.10"
  );

  assert.equal(
    getSourceIp({
      headers: {"x-forwarded-for": "198.51.100.25, 127.0.0.1"},
      socket: {remoteAddress: "127.0.0.1"}
    }, {trustProxy: true}),
    "198.51.100.25"
  );
}

main();
