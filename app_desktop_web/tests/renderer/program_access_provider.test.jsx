// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { AppRuntimeProvider } from "../../src/runtime/app_runtime_provider.jsx";
import { createAppRuntimeStore } from "../../src/runtime/app_runtime_store.js";
import { useProgramAccess } from "../../src/runtime/use_app_runtime.js";
import { ProgramAccessBanner } from "../../src/program_access/program_access_banner.jsx";
import {
  ProgramAccessProvider,
  useProgramAccessGuard,
} from "../../src/program_access/program_access_provider.jsx";


const PROGRAM_ACCESS_FIXTURE = {
  mode: "local_pass_through",
  stage: "prepackaging",
  guardEnabled: false,
  message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
  loginPlaceholderLabel: "程序会员登录后续接入",
};


function createProgramAccessError() {
  const responseText = JSON.stringify({
    detail: {
      code: "program_auth_required",
      message: "需要先登录程序会员",
    },
  });
  const error = new Error("program access rejected");
  error.responseText = responseText;
  return error;
}


function createDeviceConflictError() {
  const responseText = JSON.stringify({
    detail: {
      code: "program_device_conflict",
      message: "当前程序会员已在另一台设备登录",
    },
  });
  const error = new Error("program access rejected");
  error.responseText = responseText;
  return error;
}


function createRemoteUnavailableError() {
  const responseText = JSON.stringify({
    detail: {
      code: "program_remote_unavailable",
      message: "program access remote unavailable",
    },
  });
  const error = new Error("program access rejected");
  error.responseText = responseText;
  return error;
}


function GuardOutletProbe({ errorFactory }) {
  const {
    lastGuardError,
    runProgramAccessAction,
  } = useProgramAccessGuard();
  const [status, setStatus] = useState("idle");

  async function trigger() {
    try {
      await runProgramAccessAction(async () => {
        throw errorFactory();
      });
    } catch {
      setStatus("rejected");
    }
  }

  return (
    <>
      <ProgramAccessBanner access={PROGRAM_ACCESS_FIXTURE} guardError={lastGuardError} />
      <button type="button" onClick={() => void trigger()}>
        trigger guard
      </button>
      <span>{status}</span>
    </>
  );
}


function ProgramAuthBridgeProbe() {
  const {
    lastProgramAuthError,
    loginProgramAuth,
    verifyRegisterCode,
    completeRegisterProgramAuth,
    refreshProgramAuthStatus,
  } = useProgramAccessGuard();
  const programAccess = useProgramAccess();
  const [status, setStatus] = useState("idle");

  async function triggerStatus() {
    try {
      await refreshProgramAuthStatus();
      setStatus("status-loaded");
    } catch {
      setStatus("status-failed");
    }
  }

  async function triggerLogin() {
    try {
      await loginProgramAuth({
        username: "member_a",
        password: "pw-1",
      });
      setStatus("login-loaded");
    } catch {
      setStatus("login-failed");
    }
  }

  async function triggerVerify() {
    try {
      await verifyRegisterCode({
        email: "alice@example.com",
        code: "123456",
      });
      setStatus("verify-loaded");
    } catch {
      setStatus("verify-failed");
    }
  }

  async function triggerComplete() {
    try {
      await completeRegisterProgramAuth({
        verificationTicket: "ticket_1",
        username: "alice",
        password: "Secret123!",
      });
      setStatus("complete-loaded");
    } catch {
      setStatus("complete-failed");
    }
  }

  return (
    <>
      <button type="button" onClick={() => void triggerStatus()}>
        load status
      </button>
      <button type="button" onClick={() => void triggerLogin()}>
        trigger program auth login
      </button>
      <button type="button" onClick={() => void triggerVerify()}>
        trigger program auth verify
      </button>
      <button type="button" onClick={() => void triggerComplete()}>
        trigger program auth complete
      </button>
      <span data-testid="program-auth-status">{status}</span>
      <span data-testid="program-auth-auth-state">{programAccess.authState || "none"}</span>
      <span data-testid="program-auth-runtime-state">{programAccess.runtimeState || "none"}</span>
      <span data-testid="program-auth-error-code">{lastProgramAuthError?.code || "none"}</span>
    </>
  );
}


function ProgramAuthRegistrationVersionProbe() {
  const {
    refreshProgramAuthStatus,
    verifyRegisterCode,
    completeRegisterProgramAuth,
  } = useProgramAccessGuard();
  const [status, setStatus] = useState("idle");

  async function triggerStatus() {
    try {
      await refreshProgramAuthStatus();
      setStatus("status-loaded");
    } catch {
      setStatus("status-failed");
    }
  }

  return (
    <>
      <button type="button" onClick={() => void triggerStatus()}>
        load status
      </button>
      <span data-testid="registration-version-status">{status}</span>
      <span data-testid="has-register-v3-verify">{String(Boolean(verifyRegisterCode))}</span>
      <span data-testid="has-register-v3-complete">{String(Boolean(completeRegisterProgramAuth))}</span>
    </>
  );
}


describe("program access provider", () => {
  it("routes recognized program access errors into the shared outlet", async () => {
    render(
      <ProgramAccessProvider>
        <GuardOutletProbe errorFactory={createProgramAccessError} />
      </ProgramAccessProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger guard" }));

    expect(await screen.findByText("请先登录")).toBeInTheDocument();
    expect(screen.queryByText("需要先登录程序会员")).not.toBeInTheDocument();
    expect(screen.queryByText("program_auth_required")).not.toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();
  });

  it("ignores non-program-access errors", async () => {
    render(
      <ProgramAccessProvider>
        <GuardOutletProbe errorFactory={() => new Error("network down")} />
      </ProgramAccessProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger guard" }));

    expect(await screen.findByText("rejected")).toBeInTheDocument();
    expect(screen.queryByText("network down")).not.toBeInTheDocument();
    expect(screen.queryByText("program_auth_required")).not.toBeInTheDocument();
  });

  it("recognizes future remote guard codes through the same shared outlet", async () => {
    render(
      <ProgramAccessProvider>
        <GuardOutletProbe errorFactory={createDeviceConflictError} />
      </ProgramAccessProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger guard" }));

    expect(await screen.findByText("当前会员已在另一台设备登录")).toBeInTheDocument();
    expect(screen.queryByText("当前程序会员已在另一台设备登录")).not.toBeInTheDocument();
    expect(screen.queryByText("program_device_conflict")).not.toBeInTheDocument();
  });

  it("surfaces remote control-plane outages through the shared outlet copy", async () => {
    render(
      <ProgramAccessProvider>
        <GuardOutletProbe errorFactory={createRemoteUnavailableError} />
      </ProgramAccessProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger guard" }));

    expect(await screen.findByText("服务器连接失败请检查网络设置。")).toBeInTheDocument();
    expect(screen.queryByText("program access remote unavailable")).not.toBeInTheDocument();
    expect(screen.queryByText("program_remote_unavailable")).not.toBeInTheDocument();
  });

  it("syncs program-auth status into the runtime store through the provider bridge", async () => {
    const store = createAppRuntimeStore();
    const programAuthClient = {
      getProgramAuthStatus: async () => ({
        mode: "remote_entitlement",
        stage: "packaged_release",
        guard_enabled: true,
        message: "程序会员控制面已接入",
        auth_state: "active",
        runtime_state: "running",
        grace_expires_at: "2026-04-17T08:00:00Z",
        last_error_code: null,
      }),
      loginProgramAuth: async () => ({
        ok: true,
        message: "登录成功",
        summary: {
          mode: "remote_entitlement",
          stage: "packaged_release",
          guard_enabled: true,
          message: "程序会员已解锁",
          auth_state: "active",
          runtime_state: "running",
          grace_expires_at: "2026-04-17T08:00:00Z",
          last_error_code: null,
        },
      }),
      logoutProgramAuth: async () => {
        throw new Error("not used");
      },
    };

    render(
      <AppRuntimeProvider store={store}>
        <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={store}>
          <ProgramAuthBridgeProbe />
        </ProgramAccessProvider>
      </AppRuntimeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "load status" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("status-loaded");
    expect(screen.getByTestId("program-auth-auth-state")).toHaveTextContent("active");
    expect(screen.getByTestId("program-auth-runtime-state")).toHaveTextContent("running");
    expect(screen.getByTestId("program-auth-error-code")).toHaveTextContent("none");

    fireEvent.click(screen.getByRole("button", { name: "trigger program auth login" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("login-loaded");
    expect(screen.getByTestId("program-auth-auth-state")).toHaveTextContent("active");
    expect(screen.getByTestId("program-auth-runtime-state")).toHaveTextContent("running");
  });

  it("captures stub program-auth login errors through the same provider bridge", async () => {
    const store = createAppRuntimeStore();
    const error = new Error("program auth not ready");
    error.responseText = JSON.stringify({
      detail: {
        code: "program_auth_not_ready",
        message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
        mode: "local_pass_through",
        stage: "prepackaging",
      },
    });
    const programAuthClient = {
      getProgramAuthStatus: async () => ({
        mode: "local_pass_through",
        stage: "prepackaging",
        guard_enabled: false,
        message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
        auth_state: null,
        runtime_state: null,
        grace_expires_at: null,
        last_error_code: null,
      }),
      loginProgramAuth: async () => {
        throw error;
      },
      logoutProgramAuth: async () => {
        throw new Error("not used");
      },
    };

    render(
      <AppRuntimeProvider store={store}>
        <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={store}>
          <ProgramAuthBridgeProbe />
        </ProgramAccessProvider>
      </AppRuntimeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger program auth login" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("login-failed");
    expect(screen.getByTestId("program-auth-error-code")).toHaveTextContent("program_auth_not_ready");
  });

  it("captures non-program login validation errors through the provider bridge", async () => {
    const store = createAppRuntimeStore();
    const error = new Error("invalid credentials");
    error.responseText = JSON.stringify({
      detail: {
        code: "invalid_credentials",
        message: "invalid credentials",
        action: "program-auth.login",
      },
    });
    const programAuthClient = {
      getProgramAuthStatus: async () => ({
        mode: "remote_entitlement",
        stage: "packaged_release",
        guard_enabled: true,
        message: "请先登录程序会员",
        auth_state: null,
        runtime_state: "stopped",
        grace_expires_at: null,
        last_error_code: "program_auth_required",
      }),
      loginProgramAuth: async () => {
        throw error;
      },
      logoutProgramAuth: async () => {
        throw new Error("not used");
      },
    };

    render(
      <AppRuntimeProvider store={store}>
        <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={store}>
          <ProgramAuthBridgeProbe />
        </ProgramAccessProvider>
      </AppRuntimeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger program auth login" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("login-failed");
    expect(screen.getByTestId("program-auth-error-code")).toHaveTextContent("invalid_credentials");
  });

  it("bridges v3 verify/complete actions through the provider and keeps the shared workspace locked", async () => {
    const store = createAppRuntimeStore();
    const programAuthClient = {
      getProgramAuthStatus: async () => ({
        mode: "remote_entitlement",
        stage: "packaged_release",
        guard_enabled: true,
        message: "请先登录程序会员",
        auth_state: null,
        runtime_state: "stopped",
        grace_expires_at: null,
        last_error_code: "program_auth_required",
      }),
      loginProgramAuth: async () => {
        throw new Error("not used");
      },
      verifyRegisterCode: async () => ({
        ok: true,
        message: "验证码已验证",
        verification_ticket: "ticket_1",
        summary: {
          mode: "remote_entitlement",
          stage: "packaged_release",
          guard_enabled: true,
          message: "请先登录程序会员",
          auth_state: null,
          runtime_state: "stopped",
          grace_expires_at: null,
          last_error_code: "program_auth_required",
        },
      }),
      completeRegisterProgramAuth: async () => ({
        ok: true,
        message: "账号已创建，但当前未开通会员",
        summary: {
          mode: "remote_entitlement",
          stage: "packaged_release",
          guard_enabled: true,
          message: "请先登录程序会员",
          auth_state: null,
          runtime_state: "stopped",
          grace_expires_at: null,
          last_error_code: "program_auth_required",
        },
      }),
      logoutProgramAuth: async () => {
        throw new Error("not used");
      },
    };

    render(
      <AppRuntimeProvider store={store}>
        <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={store}>
          <ProgramAuthBridgeProbe />
        </ProgramAccessProvider>
      </AppRuntimeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger program auth verify" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("verify-loaded");
    expect(screen.getByTestId("program-auth-auth-state")).toHaveTextContent("none");
    expect(screen.getByTestId("program-auth-runtime-state")).toHaveTextContent("stopped");

    fireEvent.click(screen.getByRole("button", { name: "trigger program auth complete" }));

    expect(await screen.findByTestId("program-auth-status")).toHaveTextContent("complete-loaded");
    expect(screen.getByTestId("program-auth-auth-state")).toHaveTextContent("none");
    expect(screen.getByTestId("program-auth-runtime-state")).toHaveTextContent("stopped");
  });

  it("always exposes registration verify/complete actions without registration_flow_version gating", async () => {
    const store = createAppRuntimeStore();
    const programAuthClient = {
      getProgramAuthStatus: async () => ({
        mode: "remote_entitlement",
        stage: "packaged_release",
        guard_enabled: true,
        message: "请先登录程序会员",
        auth_state: null,
        runtime_state: "stopped",
        grace_expires_at: null,
        last_error_code: "program_auth_required",
        registration_flow_version: 2,
      }),
      loginProgramAuth: async () => {
        throw new Error("not used");
      },
      logoutProgramAuth: async () => {
        throw new Error("not used");
      },
    };

    render(
      <AppRuntimeProvider store={store}>
        <ProgramAccessProvider programAuthClient={programAuthClient} runtimeStore={store}>
          <ProgramAuthRegistrationVersionProbe />
        </ProgramAccessProvider>
      </AppRuntimeProvider>,
    );

    expect(screen.getByTestId("has-register-v3-verify")).toHaveTextContent("true");
    expect(screen.getByTestId("has-register-v3-complete")).toHaveTextContent("true");

    fireEvent.click(screen.getByRole("button", { name: "load status" }));

    expect(await screen.findByTestId("registration-version-status")).toHaveTextContent("status-loaded");
    expect(screen.getByTestId("has-register-v3-verify")).toHaveTextContent("true");
    expect(screen.getByTestId("has-register-v3-complete")).toHaveTextContent("true");
  });
});
