// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import * as React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProgramAccessSidebarCard } from "../../src/program_access/program_access_sidebar_card.jsx";

function getProgramAccessDialog() {
  return screen.getByRole("dialog");
}

async function findProgramAccessDialog() {
  return await screen.findByRole("dialog");
}

function getProgramAccessBackdrop() {
  const dialog = getProgramAccessDialog();
  const backdrop = dialog.closest(".surface-backdrop");
  if (!backdrop) {
    throw new Error("Expected dialog to be wrapped by .surface-backdrop");
  }
  return backdrop;
}

function getLoginSubmitButton() {
  const passwordInput = screen.getByPlaceholderText("请输入密码");
  const form = passwordInput.closest(".program-access-sidebar-card__form");
  if (!form) {
    throw new Error("Expected login input to be wrapped by .program-access-sidebar-card__form");
  }
  return within(form).getByRole("button", { name: "登录" });
}

function getDialogFeedbackToast() {
  return document.querySelector(".program-access-dialog__feedback-toast");
}

function expectRightAlignedSubmitAction(button) {
  const actionRow = button.closest(".program-access-dialog__actions--submit-end");
  if (!actionRow) {
    throw new Error("Expected submit button to be wrapped by a right-aligned action row");
  }
  expect(actionRow).toHaveClass("program-access-dialog__actions");
}

function expectDialogHasFixedSizingContract(dialog) {
  const hasFixedSizeData =
    dialog.getAttribute("data-fixed-size") === "true"
    || dialog.getAttribute("data-dialog-size") === "fixed";
  const hasFixedSizeClass =
    dialog.classList.contains("is-fixed-size")
    || dialog.classList.contains("program-access-dialog--fixed-size");
  const hasInlineWidthConstraint = Boolean(dialog.style.width || dialog.style.minWidth || dialog.style.maxWidth);
  const hasInlineHeightConstraint = Boolean(dialog.style.height || dialog.style.minHeight || dialog.style.maxHeight);
  const hasFixedSizeInline = hasInlineWidthConstraint && hasInlineHeightConstraint;

  // JSDOM does not apply stylesheet layout. This test enforces an observable contract:
  // data-* marker, class marker, or inline sizing constraints.
  expect(hasFixedSizeData || hasFixedSizeClass || hasFixedSizeInline).toBe(true);
}

function getDialogSizingSignature(dialog) {
  return JSON.stringify({
    dataFixedSize: dialog.getAttribute("data-fixed-size"),
    dataDialogSize: dialog.getAttribute("data-dialog-size"),
    fixedSizeClasses: Array.from(dialog.classList)
      .filter((token) => token.includes("fixed-size") || token.includes("fixed_size"))
      .sort(),
    style: {
      width: dialog.style.width,
      minWidth: dialog.style.minWidth,
      maxWidth: dialog.style.maxWidth,
      height: dialog.style.height,
      minHeight: dialog.style.minHeight,
      maxHeight: dialog.style.maxHeight,
    },
  });
}


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
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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

    expect(getProgramAccessDialog()).toBeInTheDocument();
    expect(screen.queryByText("PROGRAM ACCESS")).not.toBeInTheDocument();
    expect(screen.getByText("当前账号状态")).toBeInTheDocument();
    expect(screen.getByText("已生效")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("2026-04-17T08:00:00Z")).toBeInTheDocument();
    expect(screen.queryByText("程序账号只是当前权限钥匙，本地始终只保留一份共享数据。")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "刷新状态" })).not.toBeInTheDocument();
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

    expect(getProgramAccessDialog()).toBeInTheDocument();
    expect(screen.queryByText("PROGRAM ACCESS")).not.toBeInTheDocument();
    expect(screen.queryByText("只读锁定")).not.toBeInTheDocument();
    expect(screen.queryByText("切换程序账号只会改变当前权限，不会切换本地数据。")).not.toBeInTheDocument();
    expect(screen.queryByText("当前本地数据继续保留，只能查看，关键功能已锁定。")).not.toBeInTheDocument();
    expect(getLoginSubmitButton()).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "刷新状态" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "注册" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "找回密码" })).toBeInTheDocument();
  });

  it("shows 尚无会员 when the account is logged in but does not have membership", async () => {
    const user = userEvent.setup();

    render(
      <ProgramAccessSidebarCard
        access={{
          mode: "remote_entitlement",
          stage: "packaged_release",
          guardEnabled: true,
          message: "当前套餐暂未开放该功能",
          username: "alice",
          authState: "revoked",
          runtimeState: "stopped",
          graceExpiresAt: "",
          lastErrorCode: "program_feature_not_enabled",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    const dialog = await findProgramAccessDialog();
    expect(within(dialog).getByText("尚无会员")).toBeInTheDocument();
    expect(within(dialog).queryByText("程序会员")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("当前套餐暂未开放该功能")).not.toBeInTheDocument();
  });

  it("does not close the auth dialog when clicking the backdrop; only the X button closes it", async () => {
    const user = userEvent.setup();

    render(<ProgramAccessSidebarCard access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE} />);

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    expect(getProgramAccessDialog()).toBeInTheDocument();

    fireEvent.click(getProgramAccessBackdrop());
    expect(getProgramAccessDialog()).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
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
    fireEvent.change(screen.getByPlaceholderText("请输入账号"), {
      target: { value: "member_remote" },
    });
    fireEvent.change(screen.getByPlaceholderText("请输入密码"), {
      target: { value: "pw-remote" },
    });
    fireEvent.click(getLoginSubmitButton());

    await waitFor(() => {
      expect(loginProgramAuth).toHaveBeenCalledWith({
        username: "member_remote",
        password: "pw-remote",
      });
    });
  });

  it("shows provider auth errors in remote mode without exposing internal codes", () => {
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
    expect(screen.getByText("会员服务暂未就绪")).toBeInTheDocument();
    expect(screen.queryByText("当前为本地放行模式，远端程序会员控制面尚未接入正式链路")).not.toBeInTheDocument();
    expect(screen.queryByText("program_auth_not_ready")).not.toBeInTheDocument();
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

  it("keeps the auth dialog sizing stable and hides guard-level program_auth_required prompts", async () => {
    const user = userEvent.setup();

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        guardError={{
          code: "program_auth_required",
          message: "请先登录程序会员",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    const dialog = await findProgramAccessDialog();
    const loginSignature = getDialogSizingSignature(dialog);
    expect(screen.queryByText("请先登录程序会员")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(getDialogSizingSignature(getProgramAccessDialog())).toBe(loginSignature);
    expect(screen.queryByText("请先登录程序会员")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "找回密码" }));
    expect(getDialogSizingSignature(getProgramAccessDialog())).toBe(loginSignature);
    expect(screen.queryByText("请先登录程序会员")).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "发送注册验证码" })).toBeEnabled();

    await user.clear(screen.getByLabelText("注册邮箱"));
    await user.type(screen.getByLabelText("注册邮箱"), "1822049852@qq.CO");
    expect(screen.getByRole("button", { name: "发送注册验证码" })).toBeEnabled();

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
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

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

    const sendButton = screen.getByRole("button", { name: "发送注册验证码 (60s)" });
    const cancelButton = screen.getByRole("button", { name: "取消" });
    expect(
      sendButton.compareDocumentPosition(cancelButton) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await user.click(cancelButton);
    expect(await screen.findByLabelText("注册验证码")).toBeInTheDocument();
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

  it("keeps the register email draft when switching between register/login/reset and back", async () => {
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
    expect(screen.getByLabelText("注册邮箱")).toHaveValue("alice@example.com");

    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(screen.getByPlaceholderText("请输入账号")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "找回密码" }));
    expect(screen.getByLabelText("找回密码邮箱")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(screen.getByLabelText("注册邮箱")).toHaveValue("alice@example.com");
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

    const dialog = await findProgramAccessDialog();
    expect(within(dialog).getByText("c5交易助手")).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "登录" })).toBeInTheDocument();

    const closeButton = screen.getByRole("button", { name: "关闭" });
    expect(closeButton).toHaveTextContent("X");

    expect(screen.getByPlaceholderText("请输入账号")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("请输入密码")).toBeInTheDocument();
    expectDialogHasFixedSizingContract(dialog);

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(screen.getByLabelText("注册邮箱")).toHaveAttribute("placeholder", "请输入注册邮箱");

    await user.type(screen.getByLabelText("注册邮箱"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(await screen.findByLabelText("注册验证码")).toHaveAttribute("placeholder", "请输入验证码");
  });

  it("keeps a stable sizing contract when switching between login/register/reset flows", async () => {
    const user = userEvent.setup();

    render(<ProgramAccessSidebarCard access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE} />);

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    const dialog = await findProgramAccessDialog();
    expectDialogHasFixedSizingContract(dialog);
    const loginSignature = getDialogSizingSignature(dialog);

    await user.click(screen.getByRole("button", { name: "注册" }));
    expect(getDialogSizingSignature(getProgramAccessDialog())).toBe(loginSignature);

    await user.click(screen.getByRole("button", { name: "找回密码" }));
    expect(getDialogSizingSignature(getProgramAccessDialog())).toBe(loginSignature);
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

    const visibilityToggle = screen.getByRole("button", { name: "显示密码明文" });
    expect(screen.getByLabelText("新密码")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("再次输入新密码")).toHaveAttribute("type", "password");
    await user.click(visibilityToggle);
    expect(screen.getByLabelText("新密码")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("再次输入新密码")).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "隐藏密码明文" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("找回密码验证码"), "654321");
    await user.type(screen.getByLabelText("新密码"), "NewSecret456!");
    await user.type(screen.getByLabelText("再次输入新密码"), "NewSecret456!");
    await user.click(screen.getByRole("button", { name: "提交新密码" }));

    expect(resetProgramAuthPassword).toHaveBeenCalledWith({
      email: "alice@example.com",
      code: "654321",
      newPassword: "NewSecret456!",
    });
    expect(await screen.findByText("密码已重置")).toBeInTheDocument();
    expect(screen.queryByText("只读锁定")).not.toBeInTheDocument();
  });

  it("blocks reset submit when the confirmation password does not match", async () => {
    const user = userEvent.setup();
    const resetProgramAuthPassword = vi.fn();

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        resetProgramAuthPassword={resetProgramAuthPassword}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "找回密码" }));
    await user.type(screen.getByLabelText("找回密码邮箱"), "alice@example.com");
    await user.type(screen.getByLabelText("找回密码验证码"), "654321");
    await user.type(screen.getByLabelText("新密码"), "NewSecret456!");
    await user.type(screen.getByLabelText("再次输入新密码"), "Mismatch456!");
    await user.click(screen.getByRole("button", { name: "提交新密码" }));

    expect(resetProgramAuthPassword).not.toHaveBeenCalled();
    const toast = screen.getByRole("alert");
    expect(toast).toHaveTextContent("两次输入的新密码不一致。");
    expect(getDialogFeedbackToast()).toBe(toast);
  });

  it("shows reset validation errors as a centered dialog toast instead of a bottom block", async () => {
    const user = userEvent.setup();

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "找回密码" }));
    await user.click(screen.getByRole("button", { name: "提交新密码" }));

    const toast = screen.getByRole("alert");
    expect(toast).toHaveTextContent("请先填写完整的找回密码信息。");
    expect(getDialogFeedbackToast()).toBe(toast);
    expect(screen.queryByText("请先填写完整的找回密码信息。", {
      selector: ".program-access-sidebar-card__error",
    })).not.toBeInTheDocument();
  });

  it("does not silently swallow invalid register email when sending verification code", async () => {
    const user = userEvent.setup();
    const sendRegisterCode = vi.fn();

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
    await user.type(screen.getByLabelText("注册邮箱"), "abc@@");
    await user.click(screen.getByRole("button", { name: "发送注册验证码" }));

    expect(sendRegisterCode).not.toHaveBeenCalled();
    const toast = screen.getByRole("alert");
    expect(toast).toHaveTextContent("请输入有效邮箱地址。");
    expect(getDialogFeedbackToast()).toBe(toast);
  });

  it("shows an explicit reset send-code error for invalid email instead of silently trying", async () => {
    const user = userEvent.setup();
    const sendResetPasswordCode = vi.fn();

    render(
      <ProgramAccessSidebarCard
        access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE}
        sendResetPasswordCode={sendResetPasswordCode}
      />,
    );

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));
    await user.click(screen.getByRole("button", { name: "找回密码" }));
    await user.type(screen.getByLabelText("找回密码邮箱"), "abc@@");
    await user.click(screen.getByRole("button", { name: "发送找回密码验证码" }));

    expect(sendResetPasswordCode).not.toHaveBeenCalled();
    const toast = screen.getByRole("alert");
    expect(toast).toHaveTextContent("请输入有效邮箱地址。");
    expect(getDialogFeedbackToast()).toBe(toast);
  });

  it("keeps auth tabs dense and right-aligns the login and reset submit actions", async () => {
    const user = userEvent.setup();

    render(<ProgramAccessSidebarCard access={REMOTE_PROGRAM_ACCESS_LOGGED_OUT_FIXTURE} />);

    await user.click(screen.getByRole("button", { name: "打开程序账号窗口" }));

    expect(getProgramAccessDialog()).toHaveClass("program-access-dialog--compact-shell");
    expect(getProgramAccessDialog()).toHaveClass("program-access-dialog--dense-controls");
    const authModeTabs = screen.getByLabelText("程序会员模式");
    expect(within(authModeTabs).getByRole("button", { name: "登录" })).toHaveClass("program-access-sidebar-card__tab--dense");
    expect(within(authModeTabs).getByRole("button", { name: "注册" })).toHaveClass("program-access-sidebar-card__tab--dense");
    expect(within(authModeTabs).getByRole("button", { name: "找回密码" })).toHaveClass("program-access-sidebar-card__tab--dense");
    expect(screen.getByPlaceholderText("请输入账号")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(screen.getByPlaceholderText("请输入密码")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(getLoginSubmitButton()).toHaveClass("program-access-sidebar-card__button--compact");
    expectRightAlignedSubmitAction(getLoginSubmitButton());
    expect(screen.queryByRole("button", { name: "刷新状态" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "找回密码" }));
    expect(screen.getByLabelText("找回密码邮箱")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(screen.getByLabelText("找回密码验证码")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(screen.getByLabelText("新密码")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(screen.getByLabelText("再次输入新密码")).toHaveClass("program-access-sidebar-card__input--compact");
    expect(screen.getByRole("button", { name: "发送找回密码验证码" })).toHaveClass("program-access-sidebar-card__button--compact");
    expect(screen.getByRole("button", { name: "提交新密码" })).toHaveClass("program-access-sidebar-card__button--compact");
    const passwordToggle = screen.getByRole("button", { name: "显示密码明文" });
    expect(passwordToggle).toHaveClass("program-access-sidebar-card__button--compact");
    expect(passwordToggle).toHaveClass("program-access-sidebar-card__password-toggle");
    expect(passwordToggle.closest(".program-access-sidebar-card__inline--password")).not.toBeNull();
    expect(screen.getByLabelText("新密码").closest(".program-access-sidebar-card__password-field")).not.toBeNull();
    expectRightAlignedSubmitAction(screen.getByRole("button", { name: "提交新密码" }));
  });
});
