const UNLOCKED_AUTH_STATES = new Set(["active", "grace", "refresh_due"]);


export function hasRemoteProgramSession(access) {
  return UNLOCKED_AUTH_STATES.has(String(access?.authState || ""));
}


export function isProgramReadonlyLocked(access) {
  if (access?.mode !== "remote_entitlement") {
    return false;
  }

  if (!access?.guardEnabled) {
    return false;
  }

  return !hasRemoteProgramSession(access);
}
