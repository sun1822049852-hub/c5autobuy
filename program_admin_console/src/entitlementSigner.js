const crypto = require("node:crypto");
const fs = require("node:fs");
const {DEFAULTS, PATHS} = require("./constants");

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function toText(value = "") {
  return String(value == null ? "" : value).trim();
}

let generatedFallbackPrivateKey = null;

function getGeneratedFallbackPrivateKey() {
  if (!generatedFallbackPrivateKey) {
    const {privateKey} = crypto.generateKeyPairSync("ed25519");
    generatedFallbackPrivateKey = privateKey;
  }
  return generatedFallbackPrivateKey;
}

function resolvePrivateKey(privateKeyFile = "") {
  const explicitPath = toText(privateKeyFile);
  const filePath = toText(privateKeyFile) || PATHS.DEFAULT_PRIVATE_KEY_FILE;
  if (fs.existsSync(filePath)) {
    return crypto.createPrivateKey(fs.readFileSync(filePath, "utf8"));
  }
  if (explicitPath) {
    throw new Error(`private key not found: ${filePath}`);
  }
  return getGeneratedFallbackPrivateKey();
}

function deriveKeyId(privateKey) {
  const publicDer = crypto.createPublicKey(privateKey).export({type: "spki", format: "der"});
  const fingerprint = crypto.createHash("sha256").update(publicDer).digest("base64url");
  return `ed25519:${fingerprint.slice(0, 32)}`;
}

function resolveKeyId(privateKey, keyId = "") {
  const explicitKeyId = toText(keyId);
  const derivedKeyId = deriveKeyId(privateKey);
  if (explicitKeyId && explicitKeyId !== derivedKeyId) {
    throw new Error(`configured signing kid "${explicitKeyId}" does not match derived kid "${derivedKeyId}"`);
  }
  return explicitKeyId || derivedKeyId;
}

function publicKeyToPem(publicKey) {
  return publicKey.export({type: "spki", format: "pem"}).toString("utf8");
}

function publicKeyToJwk(publicKey, keyId = "") {
  const jwk = publicKey.export({format: "jwk"});
  return {
    kty: "OKP",
    crv: "Ed25519",
    kid: toText(keyId) || deriveKeyId(publicKey),
    x: toText(jwk && jwk.x)
  };
}

function parsePublishedKeySet(rawText = "") {
  const normalized = toText(rawText);
  if (!normalized) {
    return [];
  }
  if (normalized.includes("BEGIN PUBLIC KEY")) {
    const publicKey = crypto.createPublicKey(normalized);
    return [{
      kid: deriveKeyId(publicKey),
      publicKey
    }];
  }
  const payload = JSON.parse(normalized);
  const keys = Array.isArray(payload && payload.keys) ? payload.keys : [];
  return keys.flatMap((entry) => {
    if (!entry || typeof entry !== "object") {
      return [];
    }
    if (toText(entry.kty) !== "OKP" || toText(entry.crv) !== "Ed25519" || !toText(entry.x)) {
      return [];
    }
    const publicKey = crypto.createPublicKey({
      key: {
        kty: "OKP",
        crv: "Ed25519",
        x: toText(entry.x)
      },
      format: "jwk"
    });
    const kid = toText(entry.kid) || deriveKeyId(publicKey);
    return [{kid, publicKey}];
  });
}

function resolvePublishedKeys({
  publicKey,
  keyId = "",
  publicKeySetFile = ""
} = {}) {
  const keysByKid = new Map();
  const currentKeyId = toText(keyId) || deriveKeyId(publicKey);
  keysByKid.set(currentKeyId, publicKey);
  const explicitPath = toText(publicKeySetFile);
  if (explicitPath) {
    if (!fs.existsSync(explicitPath)) {
      throw new Error(`public key set not found: ${explicitPath}`);
    }
    const rawText = fs.readFileSync(explicitPath, "utf8");
    for (const entry of parsePublishedKeySet(rawText)) {
      if (!keysByKid.has(entry.kid)) {
        keysByKid.set(entry.kid, entry.publicKey);
      }
    }
  }
  return [...keysByKid.entries()].map(([kid, candidatePublicKey]) => ({
    kid,
    publicKey: candidatePublicKey,
    publicKeyPem: publicKeyToPem(candidatePublicKey),
    jwk: publicKeyToJwk(candidatePublicKey, kid)
  }));
}

function createEntitlementSigner({
  privateKeyFile = "",
  keyId = "",
  publicKeySetFile = "",
  iss = "c5-control-plane",
  aud = "c5-client",
  now = () => new Date(),
  snapshotTtlMinutes = DEFAULTS.SNAPSHOT_TTL_MINUTES,
  runtimePermitTtlSeconds = DEFAULTS.RUNTIME_PERMIT_TTL_SECONDS
} = {}) {
  const privateKey = resolvePrivateKey(privateKeyFile);
  const publicKey = crypto.createPublicKey(privateKey);
  const resolvedKid = resolveKeyId(privateKey, keyId);
  const publicKeyPem = publicKeyToPem(publicKey);
  const publishedKeys = resolvePublishedKeys({
    publicKey,
    keyId: resolvedKid,
    publicKeySetFile
  });

  function signSnapshot(snapshot) {
    return crypto.sign(null, Buffer.from(stableStringify(snapshot)), privateKey).toString("base64");
  }

  return {
    keyId: resolvedKid,
    publicKeyPem,
    publicJwks: {
      keys: publishedKeys.map((entry) => entry.jwk)
    },
    issueBundle({
      user = null,
      deviceId = "",
      permissions = [],
      featureFlags = {}
    } = {}) {
      if (!user || typeof user !== "object") {
        throw new Error("user is required");
      }
      if (!toText(deviceId)) {
        throw new Error("device_id is required");
      }
      const issuedAt = now();
      const iatDate = issuedAt instanceof Date ? issuedAt : new Date(issuedAt);
      const expDate = new Date(
        iatDate.getTime() + Math.max(1, Number(snapshotTtlMinutes) || DEFAULTS.SNAPSHOT_TTL_MINUTES) * 60 * 1000
      );
      const snapshot = {
        iss,
        aud,
        sub: toText(user.id),
        username: toText(user.username),
        membership_plan: toText(user.membership_plan) || "inactive",
        device_id: toText(deviceId),
        permissions: Array.isArray(permissions) ? [...permissions] : [],
        feature_flags: featureFlags && typeof featureFlags === "object" ? {...featureFlags} : {},
        iat: iatDate.toISOString(),
        exp: expDate.toISOString()
      };
      return {
        snapshot,
        signature: signSnapshot(snapshot),
        kid: resolvedKid
      };
    },
    issueRuntimePermit({
      user = null,
      deviceId = "",
      action = "runtime.start",
      ttlSeconds = runtimePermitTtlSeconds
    } = {}) {
      if (!user || typeof user !== "object") {
        throw new Error("user is required");
      }
      if (!toText(deviceId)) {
        throw new Error("device_id is required");
      }
      const actionCode = toText(action);
      if (!actionCode) {
        throw new Error("action is required");
      }
      const issuedAt = now();
      const iatDate = issuedAt instanceof Date ? issuedAt : new Date(issuedAt);
      const expDate = new Date(
        iatDate.getTime() + Math.max(1, Number(ttlSeconds) || DEFAULTS.RUNTIME_PERMIT_TTL_SECONDS) * 1000
      );
      const snapshot = {
        iss,
        aud,
        sub: toText(user.id),
        username: toText(user.username),
        membership_plan: toText(user.membership_plan) || "inactive",
        device_id: toText(deviceId),
        action: actionCode,
        iat: iatDate.toISOString(),
        exp: expDate.toISOString()
      };
      return {
        snapshot,
        signature: signSnapshot(snapshot),
        kid: resolvedKid
      };
    }
  };
}

module.exports = {
  createEntitlementSigner
};
