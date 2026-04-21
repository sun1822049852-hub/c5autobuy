import { describe, expect, it, vi } from "vitest";

import { createProgramAuthClient } from "../../src/api/program_auth_client.js";


describe("program auth client", () => {
  it("loads local program auth status and submits login/logout actions", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ mode: "remote_entitlement", auth_state: null, message: "请先登录程序会员" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "登录成功", summary: { auth_state: "active" } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "已退出登录", summary: { auth_state: null } }),
      });
    const client = createProgramAuthClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const status = await client.getProgramAuthStatus();
    const loginResult = await client.loginProgramAuth({
      username: "alice",
      password: "Secret123!",
    });
    const logoutResult = await client.logoutProgramAuth();

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/program-auth/status",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/program-auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          username: "alice",
          password: "Secret123!",
        }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8123/program-auth/logout",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({}),
      }),
    );
    expect(status.message).toBe("请先登录程序会员");
    expect(loginResult.message).toBe("登录成功");
    expect(logoutResult.message).toBe("已退出登录");
  });

  it("submits register and reset-password flows through the local backend contract", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "注册验证码已发送", summary: { auth_state: null } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "账号已创建，但当前未开通会员", summary: { auth_state: null } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "密码重置验证码已发送", summary: { auth_state: null } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, message: "密码已重置", summary: { auth_state: null } }),
      });
    const client = createProgramAuthClient({
      apiBaseUrl: "http://127.0.0.1:8123",
      fetchImpl,
    });

    const sendRegisterCodeResult = await client.sendRegisterCode({ email: "alice@example.com" });
    const registerResult = await client.registerProgramAuth({
      email: "alice@example.com",
      code: "123456",
      username: "alice",
      password: "Secret123!",
    });
    const sendResetCodeResult = await client.sendResetPasswordCode({ email: "alice@example.com" });
    const resetResult = await client.resetProgramAuthPassword({
      email: "alice@example.com",
      code: "654321",
      newPassword: "NewSecret456!",
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8123/program-auth/register/send-code",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "alice@example.com" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8123/program-auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "alice@example.com",
          code: "123456",
          username: "alice",
          password: "Secret123!",
        }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8123/program-auth/password/send-reset-code",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "alice@example.com" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8123/program-auth/password/reset",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "alice@example.com",
          code: "654321",
          new_password: "NewSecret456!",
        }),
      }),
    );
    expect(sendRegisterCodeResult.message).toBe("注册验证码已发送");
    expect(registerResult.message).toBe("账号已创建，但当前未开通会员");
    expect(sendResetCodeResult.message).toBe("密码重置验证码已发送");
    expect(resetResult.message).toBe("密码已重置");
  });
});
