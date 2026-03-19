import { createAccountCenterClient } from "./api/account_center_client.js";
import { getDesktopBootstrapConfig } from "./desktop/bridge.js";
import { AccountCenterPage } from "./features/account-center/account_center_page.jsx";
import { AppShell } from "./features/shell/app_shell.jsx";


export function App() {
  const bootstrapConfig = getDesktopBootstrapConfig();
  const client = createAccountCenterClient({
    apiBaseUrl: bootstrapConfig.apiBaseUrl,
    pollIntervalMs: 25,
  });

  return (
    <AppShell activeItem="account-center">
      <AccountCenterPage
        bootstrapConfig={bootstrapConfig}
        client={client}
      />
    </AppShell>
  );
}
