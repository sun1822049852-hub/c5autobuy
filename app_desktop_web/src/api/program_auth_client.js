import { getDesktopBootstrapConfig } from "../desktop/bridge.js";
import { createHttpClient } from "./http.js";


export function createProgramAuthClient({
  apiBaseUrl,
  fetchImpl,
} = {}) {
  const bootstrapConfig = getDesktopBootstrapConfig();
  const resolvedApiBaseUrl = apiBaseUrl ?? bootstrapConfig.apiBaseUrl;
  const http = createHttpClient({
    baseUrl: resolvedApiBaseUrl,
    fetchImpl,
  });

  return {
    async getProgramAuthStatus() {
      return http.getJson("/program-auth/status", {
        method: "GET",
      });
    },
    async loginProgramAuth(payload) {
      return http.postJson("/program-auth/login", payload);
    },
    async logoutProgramAuth() {
      return http.postJson("/program-auth/logout", {});
    },
    async sendRegisterCode(payload) {
      return http.postJson("/program-auth/register/send-code", payload);
    },
    async registerProgramAuth(payload) {
      return http.postJson("/program-auth/register", payload);
    },
    async sendResetPasswordCode(payload) {
      return http.postJson("/program-auth/password/send-reset-code", payload);
    },
    async resetProgramAuthPassword(payload) {
      return http.postJson("/program-auth/password/reset", {
        email: payload.email,
        code: payload.code,
        new_password: payload.newPassword,
      });
    },
  };
}
