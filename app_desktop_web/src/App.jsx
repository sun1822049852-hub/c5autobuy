import { useState } from "react";

import { createAccountCenterClient } from "./api/account_center_client.js";
import { getDesktopBootstrapConfig } from "./desktop/bridge.js";
import { AccountCenterPage } from "./features/account-center/account_center_page.jsx";
import { PurchaseSystemPage } from "./features/purchase-system/purchase_system_page.jsx";
import { QuerySystemPage } from "./features/query-system/query_system_page.jsx";
import { AppShell } from "./features/shell/app_shell.jsx";


export function App() {
  const [bootstrapConfig] = useState(() => getDesktopBootstrapConfig());
  const [activeItem, setActiveItem] = useState("account-center");
  const [client] = useState(() => createAccountCenterClient({
    apiBaseUrl: bootstrapConfig.apiBaseUrl,
    pollIntervalMs: 25,
  }));

  return (
    <AppShell activeItem={activeItem} onSelect={setActiveItem}>
      {activeItem === "query-system" ? (
        <QuerySystemPage
          bootstrapConfig={bootstrapConfig}
          client={client}
        />
      ) : activeItem === "purchase-system" ? (
        <PurchaseSystemPage
          bootstrapConfig={bootstrapConfig}
          client={client}
        />
      ) : (
        <AccountCenterPage
          bootstrapConfig={bootstrapConfig}
          client={client}
        />
      )}
    </AppShell>
  );
}
