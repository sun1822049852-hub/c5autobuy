import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { resolveProgramAccessMessage } from "./program_access_messages.js";


const PROGRAM_ACCESS_CODES = new Set([
  "program_auth_required",
  "program_membership_expired",
  "program_membership_service_unavailable",
  "program_feature_not_enabled",
  "program_device_conflict",
  "program_permit_denied",
  "program_grace_limited",
  "program_guard_bypassed_dev_only",
]);

const DEFAULT_PROGRAM_ACCESS_GUARD = Object.freeze({
  lastGuardError: null,
  lastProgramAuthError: null,
  async runProgramAccessAction(action) {
    return action();
  },
  async refreshProgramAuthStatus() {
    return null;
  },
  async loginProgramAuth() {
    return null;
  },
  async logoutProgramAuth() {
    return null;
  },
  async sendRegisterCode() {
    return null;
  },
  async registerProgramAuth() {
    return null;
  },
  async sendResetPasswordCode() {
    return null;
  },
  async resetProgramAuthPassword() {
    return null;
  },
});

const ProgramAccessGuardContext = createContext(DEFAULT_PROGRAM_ACCESS_GUARD);


function tryParseJsonPayload(rawValue) {
  if (typeof rawValue !== "string" || !rawValue.trim()) {
    return null;
  }

  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}


function extractProgramErrorDetail(error) {
  const payload = tryParseJsonPayload(String(error?.responseText || error?.message || ""));
  const detail = payload?.detail && typeof payload.detail === "object"
    ? payload.detail
    : payload;

  if (!detail || typeof detail.code !== "string" || !detail.code.startsWith("program_")) {
    return null;
  }

  return detail;
}


export function extractProgramAccessError(error) {
  const detail = extractProgramErrorDetail(error);

  if (!detail || !PROGRAM_ACCESS_CODES.has(String(detail.code || ""))) {
    return null;
  }

  return {
    action: detail.action ? String(detail.action) : "",
    code: String(detail.code),
    message: resolveProgramAccessMessage({
      code: String(detail.code),
      message: String(detail.message || "程序会员校验未通过"),
    }),
  };
}


export function extractProgramAuthActionError(error) {
  const detail = extractProgramErrorDetail(error);

  if (!detail) {
    return null;
  }

  return {
    code: String(detail.code),
    message: resolveProgramAccessMessage({
      code: String(detail.code),
      message: String(detail.message || "程序会员接口暂不可用"),
    }),
    mode: detail.mode ? String(detail.mode) : "",
    stage: detail.stage ? String(detail.stage) : "",
  };
}


function syncProgramAccessSummary(runtimeStore, summary) {
  if (!summary || typeof summary !== "object") {
    return;
  }

  if (typeof runtimeStore?.applyProgramAccess === "function") {
    runtimeStore.applyProgramAccess(summary);
    return;
  }

  runtimeStore?.applyBootstrap?.({
    program_access: summary,
  });
}


function extractProgramAuthSummary(result) {
  if (!result || typeof result !== "object") {
    return null;
  }

  if (result.summary && typeof result.summary === "object") {
    return result.summary;
  }

  return result;
}


function resolveRegistrationFlowVersion(summary, fallback = 2) {
  const rawValue = summary?.registrationFlowVersion ?? summary?.registration_flow_version;
  const numericValue = Number(rawValue);
  return Number.isFinite(numericValue) ? numericValue : fallback;
}


export function ProgramAccessProvider({ children, programAuthClient = null, runtimeStore = null }) {
  const [lastGuardError, setLastGuardError] = useState(null);
  const [lastProgramAuthError, setLastProgramAuthError] = useState(null);
  const [registrationFlowVersion, setRegistrationFlowVersion] = useState(() => (
    resolveRegistrationFlowVersion(runtimeStore?.getSnapshot?.()?.programAccess, 2)
  ));

  useEffect(() => {
    if (!runtimeStore?.subscribe || !runtimeStore?.getSnapshot) {
      return undefined;
    }

    const syncRegistrationFlowVersion = () => {
      setRegistrationFlowVersion(
        resolveRegistrationFlowVersion(runtimeStore.getSnapshot()?.programAccess, 2),
      );
    };

    syncRegistrationFlowVersion();
    return runtimeStore.subscribe(syncRegistrationFlowVersion);
  }, [runtimeStore]);

  const syncSummary = useCallback((summary) => {
    syncProgramAccessSummary(runtimeStore, summary);
    setRegistrationFlowVersion((current) => resolveRegistrationFlowVersion(summary, current));
  }, [runtimeStore]);

  const runProgramAccessAction = useCallback(async (action) => {
    try {
      const result = await action();
      setLastGuardError(null);
      return result;
    } catch (error) {
      const guardError = extractProgramAccessError(error);
      if (guardError) {
        setLastGuardError(guardError);
      }
      throw error;
    }
  }, []);

  const refreshProgramAuthStatus = useCallback(async () => {
    if (!programAuthClient?.getProgramAuthStatus) {
      throw new Error("Program auth client unavailable");
    }

    const summary = await programAuthClient.getProgramAuthStatus();
    syncSummary(summary);
    setLastProgramAuthError(null);
    return summary;
  }, [programAuthClient, syncSummary]);

  const loginProgramAuth = useCallback(async (payload) => {
    if (!programAuthClient?.loginProgramAuth) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.loginProgramAuth(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const logoutProgramAuth = useCallback(async () => {
    if (!programAuthClient?.logoutProgramAuth) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.logoutProgramAuth();
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const sendRegisterCode = useCallback(async (payload) => {
    if (!programAuthClient?.sendRegisterCode) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.sendRegisterCode(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const registerProgramAuth = useCallback(async (payload) => {
    if (!programAuthClient?.registerProgramAuth) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.registerProgramAuth(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const verifyRegisterCode = useCallback(async (payload) => {
    if (!programAuthClient?.verifyRegisterCode) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.verifyRegisterCode(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const completeRegisterProgramAuth = useCallback(async (payload) => {
    if (!programAuthClient?.completeRegisterProgramAuth) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.completeRegisterProgramAuth(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const sendResetPasswordCode = useCallback(async (payload) => {
    if (!programAuthClient?.sendResetPasswordCode) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.sendResetPasswordCode(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const resetProgramAuthPassword = useCallback(async (payload) => {
    if (!programAuthClient?.resetProgramAuthPassword) {
      throw new Error("Program auth client unavailable");
    }

    try {
      const result = await programAuthClient.resetProgramAuthPassword(payload);
      const summary = extractProgramAuthSummary(result);
      syncSummary(summary);
      setLastProgramAuthError(null);
      return result;
    } catch (error) {
      const authError = extractProgramAuthActionError(error);
      if (authError) {
        setLastProgramAuthError(authError);
      }
      throw error;
    }
  }, [programAuthClient, syncSummary]);

  const value = useMemo(() => ({
    lastGuardError,
    lastProgramAuthError,
    runProgramAccessAction,
    refreshProgramAuthStatus,
    loginProgramAuth,
    logoutProgramAuth,
    sendRegisterCode,
    registerProgramAuth,
    verifyRegisterCode: registrationFlowVersion === 3 ? verifyRegisterCode : undefined,
    completeRegisterProgramAuth: registrationFlowVersion === 3 ? completeRegisterProgramAuth : undefined,
    sendResetPasswordCode,
    resetProgramAuthPassword,
  }), [
    lastGuardError,
    lastProgramAuthError,
    runProgramAccessAction,
    refreshProgramAuthStatus,
    loginProgramAuth,
    logoutProgramAuth,
    sendRegisterCode,
    registerProgramAuth,
    registrationFlowVersion,
    verifyRegisterCode,
    completeRegisterProgramAuth,
    sendResetPasswordCode,
    resetProgramAuthPassword,
  ]);

  return (
    <ProgramAccessGuardContext.Provider value={value}>
      {children}
    </ProgramAccessGuardContext.Provider>
  );
}


export function useProgramAccessGuard() {
  return useContext(ProgramAccessGuardContext);
}
