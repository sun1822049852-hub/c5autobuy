// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import * as React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProgramAccessSidebarCard } from "../../src/program_access/program_access_sidebar_card.jsx";


const LOCAL_PROGRAM_ACCESS_FIXTURE = {
  mode: "local_pass_through",
  stage: "prepackaging",
  guardEnabled: false,
  message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
};

const REMOTE_PROGRAM_ACCESS_ACTIVE_FIXTURE = {
  mode: "remote_entitlement",
  stage: "packaged_release",
  guardEnabled: true,
  message: "程序会员控制面已接入",
  username: "alice",
  authState: "active",
  runtimeState: "running",
  graceExpiresAt: "2026-04-17T08:00:00Z",
  lastErrorCode: null,
};

const REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE = {
  mode: "remote_entitlement",
  stage: "packaged_release",
  guardEnabled: true,
  message: "请先登录程序会员",
  username: "",
  authState: "",
  runtimeState: "stopped",
  graceExpiresAt: "",
  lastErrorCode: null,
};


describe("program access sidebar card", () => {
  it("shows a minimal sidebar entry in local pass-through mode without rendering auth forms inline", () => {
    render(<ProgramAccessSidebarCard access={LOCAL_PROGRAM_ACCESS_FIXTURE} />);

    expect(screen.getByRole("button", { name: "打开程序账号窗口" })).toBeInTheDocument();
    expect(screen.getByText("登录状态：")).toBeInTheDocument();
    expect(screen.queryByText("账号登录")).not.toBeInTheDocument();
    expect(screen.queryByText("PROGRAM ACCESS")).not.toBeInTheDocument();
    expect(screen.getByText("未登录")).toBeInTheDocument();
    expect(screen.getByText("无权限，仅只读")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "程序账号" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录密码")).not.toBeInTheDocument();
  });

  it("shows only the username on the sidebar and reveals a status-only dialog when already logged in", async () => {
    const user = userEvent.setup();

    render(<ProgramAccessSidebarCard access={REMOTE_PROGRAM_ACCESS_ACTIVE_FIXTURE} />);

    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("已授权，可编辑")).toBeInTheDocument();
    expect(screen.queryByText("账号登录")).not.toBeInTheDocument();
    expect(screen.queryByText("已生效")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "刷新状态" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    expect(screen.getByRole("dialog", { name: "程序账号" })).toBeInTheDocument();
    expect(screen.getAllByText("程序账号").length).toBeGreaterThan(0);
    expect(screen.queryByText("PROGRAM ACCESS")).not.toBeInTheDocument();
    expect(screen.getByText("当前账号状态")).toBeInTheDocument();
    expect(screen.getByText("已生效")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("2026-04-17T08:00:00Z")).toBeInTheDocument();
    expect(screen.queryByText("程序账号只是当前权限钥匙，本地始终只保留一份共享数据。")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新状态" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "退出" })).toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "注册" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员到期时间")).not.toBeInTheDocument();
  });

  it("keeps the sidebar minimal when locked and opens the login dialog on demand", async () => {
    const user = userEvent.setup();

    render(<ProgramAccessSidebarCard access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE} />);

    expect(screen.getByText("未登录")).toBeInTheDocument();
    expect(screen.getByText("无权限，仅只读")).toBeInTheDocument();
    expect(screen.queryByText("账号登录")).not.toBeInTheDocument();
    expect(screen.queryByText("只读锁定")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("程序会员登录账号")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    expect(screen.getByRole("dialog", { name: "程序账号" })).toBeInTheDocument();
    expect(screen.getAllByText("程序账号").length).toBeGreaterThan(0);
    expect(screen.queryByText("PROGRAM ACCESS")).not.toBeInTheDocument();
    expect(screen.queryByText("只读锁定")).not.toBeInTheDocument();
    expect(screen.queryByText("切换程序账号只会改变当前权限，不会切换本地数据。")).not.toBeInTheDocument();
    expect(screen.queryByText("当前本地数据继续保留，只能查看，关键功能已锁定。")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录程序会员" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新状态" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "注册" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "找回密码" })).toBeInTheDocument();
  });

  it("submits remote login credentials through the provider bridge", async () => {
    const loginProgramAuth = vi.fn().mockResolvedValue({
      ...REMOTE_PROGRAM_ACCESS_ACTIVE_FIXTURE,
    });

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        loginProgramAuth={loginProgramAuth}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    fireEvent.change(screen.getByLabelText("程序会员登录账号"), {
      target: { value: "member_remote" },
    });
    fireEvent.change(screen.getByLabelText("程序会员登录密码"), {
      target: { value: "pw-remote" },
    });
    fireEvent.click(screen.getByRole("button", { name: "登录程序会员" }));

    await waitFor(() => {
      expect(loginProgramAuth).toHaveBeenCalledWith({
        username: "member_remote",
        password: "pw-remote",
      });
    });
  });

  it("shows provider auth errors in remote mode", () => {
    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        lastProgramAuthError={{
          code: "program_auth_not_ready",
          message: "当前为本地放行模式，远端程序会员控制面尚未接入正式链路",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    expect(screen.getByText("program_auth_not_ready")).toBeInTheDocument();
    expect(screen.getByText("当前为本地放行模式，远端程序会员控制面尚未接入正式链路")).toBeInTheDocument();
  });

  it("hides the default program_auth_required prompt while still allowing other flows", async () => {
    const user = userEvent.setup();

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          lastErrorCode: "program_auth_required",
          message: "请先登录程序会员",
        }}
        lastProgramAuthError={{
          code: "program_auth_required",
          message: "请先登录程序会员",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    expect(screen.queryByText("program_auth_required")).not.toBeInTheDocument();
    expect(screen.queryByText("请先登录程序会员")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "注册" })).toBeInTheDocument();
  });

  it("routes registration through a three-step state machine when registration_flow_version=3 is enabled", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_1",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });
    const verifyRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "验证码已验证",
      verification_ticket: "ticket_1",
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });
    const completeRegisterProgramAuth = vi.fn().mockResolvedValue({
      ok: true,
      message: "账号已创建，但当前未开通会员",
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={verifyRegisterCode}
        completeRegisterProgramAuth={completeRegisterProgramAuth}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));

    expect(screen.getByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("注册邮箱"), "alice@");
    expect(screen.getByRole("button", { name: "发送注册验证码" })).toBeDisabled();

    await user.clear(screen.getByLabelText("注册邮箱"));
    await user.type(screen.getByLabelText("注册邮箱"), "1822049852@qq.CO");
    expect(screen.getByRole("button", { name: "发送注册验证码" })).toBeDisabled();

    await user.clear(screen.getByLabelText("注册邮箱"));
    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(sendRegisterCode).toHaveBeenCalledWith({ email: "alice@example.com" });
    expect(await screen.findByText("a***e@example.com")).toBeInTheDocument();
    expect(screen.getByLabelText("注册验证码")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("注册验证码"), "123456");
    await user.click(screen.getByRole("button", { name: "验证注册验证码" }));

    expect(verifyRegisterCode).toHaveBeenCalledWith({
      email: "alice@example.com",
      code: "123456",
      registerSessionId: "session_1",
    });
    expect(await screen.findByLabelText("注册用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("注册密码")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("注册用户名"), "alice");
    await user.type(screen.getByLabelText("注册密码"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "完成注册" }));

    expect(completeRegisterProgramAuth).toHaveBeenCalledWith({
      email: "alice@example.com",
      verificationTicket: "ticket_1",
      username: "alice",
      password: "Secret123!",
    });
    expect(await screen.findByText("账号已创建，但当前未开通会员")).toBeInTheDocument();
  });

  it("refreshes program auth status when entering register mode from a stale v2 bootstrap and upgrades into the v3 flow", async () => {
    const user = userEvent.setup();
    const refreshedAccess = {
      ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
      registration_flow_version: 3,
    };
    const refreshProgramAuthStatus = vi.fn();

    function RegisterFlowRefreshHarness() {
      const [access, setAccess] = React.useState({
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 2,
      });

      const handleRefreshProgramAuthStatus = React.useCallback(async () => {
        setAccess(refreshedAccess);
        return refreshedAccess;
      }, []);

      React.useEffect(() => {
        refreshProgramAuthStatus.mockImplementation(handleRefreshProgramAuthStatus);
      }, [handleRefreshProgramAuthStatus]);

      return (
        <ProgramAccessSidebarCard
          access={access}
          refreshProgramAuthStatus={refreshProgramAuthStatus}
          sendRegisterCode={vi.fn()}
          verifyRegisterCode={vi.fn()}
          completeRegisterProgramAuth={vi.fn()}
        />
      );
    }

    render(<RegisterFlowRefreshHarness />);

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));

    await waitFor(() => {
      expect(refreshProgramAuthStatus).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送注册验证码" })).toBeInTheDocument();
  });

  it("keeps the second-step verification UI after closing and reopening the dialog", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_1",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));
    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByText("a***e@example.com")).toBeInTheDocument();
    expect(screen.getByLabelText("注册验证码")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新发送验证码 (60s)" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog", { name: "程序账号" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    expect(screen.getByText("a***e@example.com")).toBeInTheDocument();
    expect(screen.getByLabelText("注册验证码")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册邮箱")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新发送验证码 (60s)" })).toBeInTheDocument();
  });

  it("keeps the resend cooldown when the user switches back to editing the email", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_1",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));
    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByRole("button", { name: "重新发送验证码 (60s)" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "修改邮箱" }));

    expect(screen.getByLabelText("注册邮箱")).toHaveValue("alice@example.com");
    expect(screen.getByRole("button", { name: "发送注册验证码 (60s)" })).toBeDisabled();
  });

  it("uses retry_after_seconds from send-code failures to continue the cooldown", async () => {
    const user = userEvent.setup();
    const cooldownPayload = {
      detail: {
        code: "REGISTER_SEND_RETRY_LATER",
        message: "register send is cooling down",
        retry_after_seconds: 42,
      },
    };
    const sendError = Object.assign(
      new Error(JSON.stringify(cooldownPayload)),
      { responseText: JSON.stringify(cooldownPayload) },
    );
    const sendRegisterCode = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        message: "注册验证码已发送",
        register_session_id: "session_1",
        masked_email: "a***e@example.com",
        resend_after_seconds: 0,
        summary: {
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        },
      })
      .mockRejectedValueOnce(sendError);

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));
    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByRole("button", { name: "重新发送验证码" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "重新发送验证码" }));

    expect(await screen.findByRole("button", { name: "重新发送验证码 (42s)" })).toBeDisabled();
  });

  it("clears the preserved registration draft when the user explicitly switches back to login", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_1",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));
    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByLabelText("注册验证码")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(screen.getByLabelText("程序会员登录账号")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(screen.getByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByText("a***e@example.com")).not.toBeInTheDocument();
  });

  it("moves the visible prompts into placeholders and renders the close button as X", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_1",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 3,
        }}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    const closeButton = screen.getByRole("button", { name: "关闭" });
    expect(closeButton).toHaveTextContent("X");

    expect(screen.getByLabelText("程序会员登录账号")).toHaveAttribute("placeholder", "请输入程序会员账号");
    expect(screen.getByLabelText("程序会员登录密码")).toHaveAttribute("placeholder", "请输入程序会员密码");

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(screen.getByLabelText("注册邮箱")).toHaveAttribute("placeholder", "请输入注册邮箱");

    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByLabelText("注册验证码")).toHaveAttribute("placeholder", "请输入验证码");
  });

  it("keeps the register entry on the email-first flow even when the bootstrap version is still 2", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "注册验证码已发送",
      register_session_id: "session_legacy_cut",
      masked_email: "a***e@example.com",
      resend_after_seconds: 60,
      summary: {
        ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
        registration_flow_version: 3,
      },
    });
    const refreshProgramAuthStatus = vi.fn().mockRejectedValue(new Error("not-ready-yet"));

    render(
      <ProgramAccessSidebarCard
        access={{
          ...REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
          registration_flow_version: 2,
        }}
        refreshProgramAuthStatus={refreshProgramAuthStatus}
        sendRegisterCode={sendRegisterCode}
        verifyRegisterCode={vi.fn()}
        completeRegisterProgramAuth={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "注册" }));

    expect(await screen.findByLabelText("注册邮箱")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册验证码")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(sendRegisterCode).toHaveBeenCalledWith({ email: "alice@example.com" });
    expect(await screen.findByLabelText("注册验证码")).toBeInTheDocument();
    expect(screen.queryByLabelText("注册用户名")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("注册密码")).not.toBeInTheDocument();
  });

  it("supports reset-password actions while keeping the shared workspace locked", async () => {
    const user = userEvent.setup();
    const sendResetPasswordCode = vi.fn().mockResolvedValue({
      ok: true,
      message: "密码重置验证码已发送",
      summary: REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
    });
    const resetProgramAuthPassword = vi.fn().mockResolvedValue({
      ok: true,
      message: "密码已重置",
      summary: REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE,
    });

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        sendResetPasswordCode={sendResetPasswordCode}
        resetProgramAuthPassword={resetProgramAuthPassword}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "找回密码" }));
    await user.type(screen.getByLabelText("找回密码邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送找回密码验证码" }));
    expect(sendResetPasswordCode).toHaveBeenCalledWith({ email: "alice@example.com" });

    await user.type(screen.getByLabelText("找回密码验证码"), "654321");
    await user.type(screen.getByLabelText("新密码"), "NewSecret456!");
    await user.click(screen.getByRole("button", { name: "提交新密码" }));

    expect(resetProgramAuthPassword).toHaveBeenCalledWith({
      email: "alice@example.com",
      code: "654321",
      newPassword: "NewSecret456!",
    });
    expect(await screen.findByText("密码已重置")).toBeInTheDocument();
    expect(screen.queryByText("只读锁定")).not.toBeInTheDocument();
  });
});
