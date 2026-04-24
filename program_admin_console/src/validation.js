const crypto = require("node:crypto");

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

function isStrongPassword(value = "") {
  const text = toText(value);
  if (text.length < 8 || text.length > 64) {
    return false;
  }
  return /[A-Za-z]/.test(text) && /\d/.test(text);
}

function isValidUsername(value = "") {
  return /^[A-Za-z0-9_]{3,32}$/.test(toText(value));
}

function generateSecureCode(length = 6) {
  const max = Math.pow(10, length);
  const min = Math.pow(10, length - 1);
  return String(min + crypto.randomInt(max - min));
}

module.exports = {
  isStrongPassword,
  isValidUsername,
  generateSecureCode
};
