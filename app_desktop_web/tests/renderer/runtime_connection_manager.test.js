// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

import { EMPTY_PROGRAM_ACCESS } from "../../src/program_access/program_access_runtime.js";
import { createRuntimeConnectionManager } from "../../src/runtime/runtime_connection_manager.js";
import { AppRuntimeProvider } from "../../src/runtime/app_runtime_provider.jsx";
import { createAppRuntimeStore } from "../../src/runtime/app_runtime_store.js";
import {
  usePatchPurchaseSystemDraft,
  usePatchPurchaseSystemUi,
  usePurchaseSystemDraft,
  usePurchaseSystemUi,
  useQuerySystemServer,
  useQuerySystemUi,
} from "../../src/runtime/use_app_runtime.js";


class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    this.onclose = null;
    FakeWebSocket.instances.push(this);
  }

  emitOpen() {
    this.onopen?.();
  }

  emitMessage(payload) {
    this.onmessage?.({
      data: JSON.stringify(payload),
    });
  }

  close() {
    this.onclose?.();
  }
}


function QuerySystemProbe() {
  const server = useQuerySystemServer();
  const ui = useQuerySystemUi();

  return createElement(
    "div",
    null,
    createElement("span", { "data-testid": "selected-config" }, ui.selectedConfigId ?? "none"),
    createElement("span", { "data-testid": "config-count" }, String(server.configs.length)),
    createElement("span", { "data-testid": "runtime-running" }, String(server.runtimeStatus.running)),
  );
}


function PurchaseSystemProbe() {
  const ui = usePurchaseSystemUi();
  const draft = usePurchaseSystemDraft();
  const patchUi = usePatchPurchaseSystemUi();
  const patchDraft = usePatchPurchaseSystemDraft();

  return createElement(
    "div",
    null,
    createElement("span", { "data-testid": "purchase-selected-config" }, ui.selectedConfigId ?? "none"),
    createElement("span", { "data-testid": "purchase-active-modal" }, ui.activeModal || "none"),
    createElement("span", { "data-testid": "purchase-draft-mode" }, draft.querySettingsDraft?.mode_type ?? "none"),
    createElement(
      "button",
      {
        type: "button",
        onClick: () => patchUi({ selectedConfigId: "pcfg-1", activeModal: "settings" }),
      },
      "patch purchase ui",
    ),
    createElement(
      "button",
      {
        type: "button",
        onClick: () => patchDraft({
          purchaseSettingsDraft: { per_batch_ip_fanout_limit: 3 },
          querySettingsDraft: { mode_type: "token" },
        }),
      },
      "patch purchase draft",
    ),
  );
}


describe("app runtime store", () => {
  const summaryConfig = (configId, name) => ({ config_id: configId, name, serverShape: "summary" });

  it("creates the expected initial snapshot and notifies subscribers", () => {
    const store = createAppRuntimeStore();
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    expect(store.getSnapshot()).toEqual({
      bootstrap: { state: "idle", hydratedAt: null, version: 0 },
      connection: { state: "idle", stale: false, lastSyncAt: null, lastEventVersion: 0, lastError: "" },
      programAccess: {
        ...EMPTY_PROGRAM_ACCESS,
        username: "",
      },
      querySystem: {
        serverHydrated: false,
        server: {
          configs: [],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: false, item_rows: [] },
        },
        ui: { selectedConfigId: null },
        draft: { currentConfig: null, hasUnsavedChanges: false },
      },
      purchaseSystem: {
        serverHydrated: false,
        server: {
          runtimeStatus: { running: false, accounts: [], item_rows: [] },
          uiPreferences: {},
          runtimeSettings: {},
        },
        ui: { selectedConfigId: null, activeModal: "" },
        draft: { purchaseSettingsDraft: {}, querySettingsDraft: null },
      },
    });

    store.patchQueryUi({ selectedConfigId: "cfg-1" });

    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    store.patchQueryUi({ selectedConfigId: "cfg-2" });

    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("applies bootstrap server state into query system server slices", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      bootstrap: {
        version: 7,
        generated_at: "2026-03-31T12:34:56.000Z",
      },
      querySystem: {
        server: {
          configs: [{ config_id: "cfg-1", name: "白天配置" }],
          capacitySummary: {
            modes: {
              new_api: { mode_type: "new_api", available_account_count: 2 },
            },
          },
          runtimeStatus: {
            running: true,
            item_rows: [{ query_item_id: "item-1" }],
          },
        },
      },
    });

    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [summaryConfig("cfg-1", "白天配置")],
      capacitySummary: {
        modes: {
          new_api: { mode_type: "new_api", available_account_count: 2 },
        },
      },
      runtimeStatus: {
        running: true,
        item_rows: [{ query_item_id: "item-1" }],
      },
    });
    expect(store.getSnapshot().bootstrap.state).toBe("hydrated");
    expect(store.getSnapshot().bootstrap.version).toBe(7);
    expect(store.getSnapshot().bootstrap.hydratedAt).toBe("2026-03-31T12:34:56.000Z");
    expect(store.getSnapshot().querySystem.serverHydrated).toBe(true);
  });

  it("marks query server hydrated even when bootstrap snapshot is legitimately empty", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      querySystem: {
        server: {
          configs: [],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: false, item_rows: [] },
        },
      },
    });

    expect(store.getSnapshot().querySystem.serverHydrated).toBe(true);
    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [],
      capacitySummary: { modes: {} },
      runtimeStatus: { running: false, item_rows: [] },
    });
  });

  it("lets query slice hydrate itself without pretending the whole app bootstrap completed", () => {
    const store = createAppRuntimeStore();

    store.applyQuerySystemServer({
      configs: [],
      capacitySummary: { modes: {} },
      runtimeStatus: { running: false, item_rows: [] },
    });

    expect(store.getSnapshot().querySystem.serverHydrated).toBe(true);
    expect(store.getSnapshot().bootstrap).toEqual({
      state: "idle",
      hydratedAt: null,
      version: 0,
    });
  });

  it("normalizes query configs without serverShape to summary at the store boundary", () => {
    const store = createAppRuntimeStore();

    store.applyQuerySystemServer({
      configs: [{ config_id: "cfg-1", name: "外部推送配置", items: [] }],
    });

    expect(store.getSnapshot().querySystem.server.configs).toEqual([
      { config_id: "cfg-1", name: "外部推送配置", items: [], serverShape: "summary" },
    ]);
  });

  it("preserves stable server shape when bootstrap payload is partial", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      querySystem: {
        server: {
          runtimeStatus: {
            running: true,
          },
        },
      },
      purchaseSystem: {
        server: {
          uiPreferences: {
            compactMode: true,
          },
        },
      },
    });

    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [],
      capacitySummary: { modes: {} },
      runtimeStatus: {
        running: true,
        item_rows: [],
      },
    });
    expect(store.getSnapshot().purchaseSystem.server).toEqual({
      runtimeStatus: { running: false, accounts: [], item_rows: [] },
      uiPreferences: { compactMode: true },
      runtimeSettings: {},
    });
  });

  it("keeps existing bootstrap metadata when payload omits server-owned fields", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      bootstrap: {
        version: 7,
        generated_at: "2026-03-31T12:34:56.000Z",
      },
    });
    store.applyBootstrap({
      querySystem: {
        server: {
          configs: [{ config_id: "cfg-2", name: "夜刀配置" }],
        },
      },
    });

    expect(store.getSnapshot().bootstrap).toEqual({
      state: "hydrated",
      version: 7,
      hydratedAt: "2026-03-31T12:34:56.000Z",
    });
  });

  it("patches query ui without mutating query server state", () => {
    const store = createAppRuntimeStore();
    const bootstrap = {
      configs: [summaryConfig("cfg-1", "白天配置")],
      capacitySummary: {
        modes: {
          new_api: { mode_type: "new_api", available_account_count: 2 },
        },
      },
      runtimeStatus: {
        running: true,
        item_rows: [{ query_item_id: "item-1" }],
      },
    };

    store.applyBootstrap({
      querySystem: {
        server: bootstrap,
      },
    });
    const serverBeforePatch = store.getSnapshot().querySystem.server;

    store.patchQueryUi({ selectedConfigId: "cfg-1" });

    expect(store.getSnapshot().querySystem.ui).toEqual({ selectedConfigId: "cfg-1" });
    expect(store.getSnapshot().querySystem.server).toEqual(bootstrap);
    expect(store.getSnapshot().querySystem.server).toBe(serverBeforePatch);
  });

  it("patches query draft without mutating query server state", () => {
    const store = createAppRuntimeStore();
    const bootstrap = {
      configs: [summaryConfig("cfg-1", "白天配置")],
      capacitySummary: {
        modes: {
          new_api: { mode_type: "new_api", available_account_count: 2 },
        },
      },
      runtimeStatus: {
        running: true,
        item_rows: [{ query_item_id: "item-1" }],
      },
    };
    const nextDraft = {
      currentConfig: { config_id: "cfg-1", name: "白天配置副本" },
      hasUnsavedChanges: true,
    };

    store.applyBootstrap({
      querySystem: {
        server: bootstrap,
      },
    });
    const serverBeforePatch = store.getSnapshot().querySystem.server;

    store.patchQueryDraft(nextDraft);

    expect(store.getSnapshot().querySystem.draft).toEqual(nextDraft);
    expect(store.getSnapshot().querySystem.server).toEqual(bootstrap);
    expect(store.getSnapshot().querySystem.server).toBe(serverBeforePatch);
  });

  it("keeps query ui and draft slices when bootstrap server data arrives later", () => {
    const store = createAppRuntimeStore();

    store.patchQueryUi({ selectedConfigId: "cfg-9" });
    store.patchQueryDraft({
      currentConfig: { config_id: "cfg-9", name: "本地草稿" },
      hasUnsavedChanges: true,
    });

    store.applyBootstrap({
      querySystem: {
        server: {
          configs: [{ config_id: "cfg-1", name: "白天配置" }],
        },
      },
    });

    expect(store.getSnapshot().querySystem.ui).toEqual({ selectedConfigId: "cfg-9" });
    expect(store.getSnapshot().querySystem.draft).toEqual({
      currentConfig: { config_id: "cfg-9", name: "本地草稿" },
      hasUnsavedChanges: true,
    });
    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [summaryConfig("cfg-1", "白天配置")],
      capacitySummary: { modes: {} },
      runtimeStatus: { running: false, item_rows: [] },
    });
  });

  it("detaches stored server state from later external payload mutations", () => {
    const store = createAppRuntimeStore();
    const payload = {
      bootstrap: {
        version: 3,
        generated_at: "2026-03-31T01:00:00.000Z",
      },
      querySystem: {
        server: {
          configs: [{ config_id: "cfg-1", name: "初始配置" }],
          runtimeStatus: {
            running: true,
            item_rows: [{ query_item_id: "item-1" }],
          },
        },
      },
      purchaseSystem: {
        server: {
          runtimeStatus: {
            running: true,
            accounts: [{ account_id: "a-1" }],
            item_rows: [{ query_item_id: "item-9" }],
          },
        },
      },
    };

    store.applyBootstrap(payload);

    payload.bootstrap.version = 99;
    payload.querySystem.server.configs[0].name = "外部污染";
    payload.querySystem.server.runtimeStatus.item_rows.push({ query_item_id: "item-2" });
    payload.purchaseSystem.server.runtimeStatus.accounts.push({ account_id: "a-2" });

    expect(store.getSnapshot().bootstrap.version).toBe(3);
    expect(store.getSnapshot().querySystem.server.configs).toEqual([summaryConfig("cfg-1", "初始配置")]);
    expect(store.getSnapshot().querySystem.server.runtimeStatus.item_rows).toEqual([{ query_item_id: "item-1" }]);
    expect(store.getSnapshot().purchaseSystem.server.runtimeStatus.accounts).toEqual([{ account_id: "a-1" }]);
  });

  it("writes query and purchase server slices from snake_case bootstrap payload", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      bootstrap: {
        version: 11,
        generated_at: "2026-03-31T15:00:00.000Z",
      },
      query_system: {
        server: {
          configs: [{ config_id: "cfg-snake", name: "蛇形配置" }],
          runtimeStatus: {
            running: true,
            item_rows: [{ query_item_id: "item-snake" }],
          },
        },
      },
      purchase_system: {
        server: {
          runtimeStatus: {
            running: true,
            accounts: [{ account_id: "a-snake" }],
            item_rows: [{ query_item_id: "purchase-item" }],
          },
          uiPreferences: {
            compactMode: true,
          },
        },
      },
    });

    expect(store.getSnapshot().bootstrap).toEqual({
      state: "hydrated",
      version: 11,
      hydratedAt: "2026-03-31T15:00:00.000Z",
    });
    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [summaryConfig("cfg-snake", "蛇形配置")],
      capacitySummary: { modes: {} },
      runtimeStatus: {
        running: true,
        item_rows: [{ query_item_id: "item-snake" }],
      },
    });
    expect(store.getSnapshot().purchaseSystem.server).toEqual({
      runtimeStatus: {
        running: true,
        accounts: [{ account_id: "a-snake" }],
        item_rows: [{ query_item_id: "purchase-item" }],
      },
      uiPreferences: {
        compactMode: true,
      },
      runtimeSettings: {},
    });
  });

  it("clears server-owned object fields when bootstrap explicitly sends empty objects", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      querySystem: {
        server: {
          capacitySummary: {
            modes: {
              new_api: { mode_type: "new_api", available_account_count: 2 },
            },
          },
        },
      },
      purchaseSystem: {
        server: {
          uiPreferences: {
            compactMode: true,
            columnOrder: ["status"],
          },
          runtimeSettings: {
            per_batch_ip_fanout_limit: 3,
          },
        },
      },
    });

    store.applyBootstrap({
      query_system: {
        server: {
          capacitySummary: {
            modes: {},
          },
        },
      },
      purchase_system: {
        server: {
          uiPreferences: {},
          runtimeSettings: {},
        },
      },
    });

    expect(store.getSnapshot().querySystem.server.capacitySummary).toEqual({ modes: {} });
    expect(store.getSnapshot().purchaseSystem.server.uiPreferences).toEqual({});
    expect(store.getSnapshot().purchaseSystem.server.runtimeSettings).toEqual({});
  });

  it("patches purchase ui and draft without mutating purchase server state", () => {
    const store = createAppRuntimeStore();

    store.applyBootstrap({
      purchaseSystem: {
        server: {
          runtimeStatus: {
            running: true,
            accounts: [{ account_id: "a-1" }],
            item_rows: [{ query_item_id: "item-1" }],
          },
        },
      },
    });
    const serverBeforePatch = store.getSnapshot().purchaseSystem.server;

    store.patchPurchaseUi({ selectedConfigId: "pcfg-1", activeModal: "settings" });
    store.patchPurchaseDraft({
      purchaseSettingsDraft: { per_batch_ip_fanout_limit: 2 },
      querySettingsDraft: { mode_type: "token" },
    });

    expect(store.getSnapshot().purchaseSystem.ui).toEqual({
      selectedConfigId: "pcfg-1",
      activeModal: "settings",
    });
    expect(store.getSnapshot().purchaseSystem.draft).toEqual({
      purchaseSettingsDraft: { per_batch_ip_fanout_limit: 2 },
      querySettingsDraft: { mode_type: "token" },
    });
    expect(store.getSnapshot().purchaseSystem.server).toBe(serverBeforePatch);
  });
});


describe("app runtime hooks", () => {
  it("reads selected slices through provider-backed selector hooks", () => {
    const store = createAppRuntimeStore();

    render(createElement(AppRuntimeProvider, { store }, createElement(QuerySystemProbe)));

    expect(screen.getByTestId("selected-config")).toHaveTextContent("none");
    expect(screen.getByTestId("config-count")).toHaveTextContent("0");
    expect(screen.getByTestId("runtime-running")).toHaveTextContent("false");

    act(() => {
      store.applyBootstrap({
        querySystem: {
          server: {
            configs: [{ config_id: "cfg-1", name: "白天配置" }],
            capacitySummary: { modes: {} },
            runtimeStatus: { running: true, item_rows: [] },
          },
        },
      });
      store.patchQueryUi({ selectedConfigId: "cfg-1" });
    });

    expect(screen.getByTestId("selected-config")).toHaveTextContent("cfg-1");
    expect(screen.getByTestId("config-count")).toHaveTextContent("1");
    expect(screen.getByTestId("runtime-running")).toHaveTextContent("true");
  });

  it("exposes purchase ui and draft patch hooks without raw store access", () => {
    const store = createAppRuntimeStore();

    render(createElement(AppRuntimeProvider, { store }, createElement(PurchaseSystemProbe)));

    expect(screen.getByTestId("purchase-selected-config")).toHaveTextContent("none");
    expect(screen.getByTestId("purchase-active-modal")).toHaveTextContent("none");
    expect(screen.getByTestId("purchase-draft-mode")).toHaveTextContent("none");

    fireEvent.click(screen.getByRole("button", { name: "patch purchase ui" }));
    fireEvent.click(screen.getByRole("button", { name: "patch purchase draft" }));

    expect(screen.getByTestId("purchase-selected-config")).toHaveTextContent("pcfg-1");
    expect(screen.getByTestId("purchase-active-modal")).toHaveTextContent("settings");
    expect(screen.getByTestId("purchase-draft-mode")).toHaveTextContent("token");
  });
});


describe("runtime connection manager", () => {
  it("connects runtime websocket updates after bootstrap and applies them into store slices", async () => {
    FakeWebSocket.instances = [];
    const store = createAppRuntimeStore();
    const client = {
      getAppBootstrap: vi.fn().mockResolvedValue({
        version: 5,
        generated_at: "2026-03-31T12:34:56.000Z",
        query_system: {
          configs: [{ config_id: "cfg-1", name: "白天配置" }],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: false, item_rows: [] },
        },
        purchase_system: {
          runtimeStatus: { running: false, accounts: [], item_rows: [] },
          uiPreferences: { selected_config_id: null, updated_at: null },
          runtimeSettings: { per_batch_ip_fanout_limit: 1, updated_at: null },
        },
      }),
    };
    const manager = createRuntimeConnectionManager({
      client,
      now: () => "2026-03-31T12:35:00.000Z",
      schedule: (callback) => {
        callback();
        return 0;
      },
      store,
    });

    await manager.bootstrap();
    const disconnect = manager.connectRuntimeUpdates({
      websocketUrl: "wss://api.example.com/ws/runtime",
      WebSocketImpl: FakeWebSocket,
      reconnectDelayMs: 0,
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe("wss://api.example.com/ws/runtime?since_version=5");

    FakeWebSocket.instances[0].emitOpen();
    FakeWebSocket.instances[0].emitMessage({
      version: 6,
      event: "query_runtime.updated",
      updated_at: "2026-03-31T12:35:01.000Z",
      payload: {
        running: true,
        config_id: "cfg-1",
        config_name: "白天配置",
        message: "运行中",
        item_rows: [{ query_item_id: "item-1" }],
      },
    });
    FakeWebSocket.instances[0].emitMessage({
      version: 7,
      event: "purchase_runtime.updated",
      updated_at: "2026-03-31T12:35:02.000Z",
      payload: {
        running: true,
        message: "运行中",
        accounts: [{ account_id: "acc-1" }],
        item_rows: [],
      },
    });
    FakeWebSocket.instances[0].emitMessage({
      version: 8,
      event: "program_access.updated",
      updated_at: "2026-03-31T12:35:03.000Z",
      payload: {
        mode: "remote_entitlement",
        stage: "packaged_release",
        guard_enabled: true,
        message: "程序会员控制面已接入",
        auth_state: "active",
        runtime_state: "running",
      },
    });

    expect(store.getSnapshot().querySystem.server.runtimeStatus).toEqual({
      running: true,
      config_id: "cfg-1",
      config_name: "白天配置",
      message: "运行中",
      item_rows: [{ query_item_id: "item-1" }],
    });
    expect(store.getSnapshot().purchaseSystem.server.runtimeStatus).toEqual({
      running: true,
      message: "运行中",
      accounts: [{ account_id: "acc-1" }],
      item_rows: [],
    });
    expect(store.getSnapshot().programAccess).toMatchObject({
      mode: "remote_entitlement",
      stage: "packaged_release",
      guardEnabled: true,
      message: "程序会员控制面已接入",
      authState: "active",
      runtimeState: "running",
    });
    expect(store.getSnapshot().connection.lastEventVersion).toBe(8);
    expect(store.getSnapshot().connection.lastSyncAt).toBe("2026-03-31T12:35:03.000Z");

    disconnect();
  });

  it("hydrates bootstrap server state and connection metadata from /app/bootstrap", async () => {
    const store = createAppRuntimeStore();
    const client = {
      getAppBootstrap: vi.fn().mockResolvedValue({
        version: 7,
        generated_at: "2026-03-31T12:34:56.000Z",
        query_system: {
          configs: [{ config_id: "cfg-1", name: "白天配置" }],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: true, item_rows: [{ query_item_id: "item-1" }] },
        },
        purchase_system: {
          runtimeStatus: { running: false, accounts: [], item_rows: [] },
          uiPreferences: { selected_config_id: "cfg-1", updated_at: "2026-03-31T12:34:56.000Z" },
          runtimeSettings: { per_batch_ip_fanout_limit: 1, updated_at: null },
        },
      }),
    };
    const now = vi.fn()
      .mockReturnValueOnce("2026-03-31T12:35:00.000Z")
      .mockReturnValueOnce("2026-03-31T12:35:00.000Z");
    const manager = createRuntimeConnectionManager({
      client,
      now,
      store,
    });

    const payload = await manager.bootstrap();

    expect(payload.version).toBe(7);
    expect(client.getAppBootstrap).toHaveBeenCalledTimes(1);
    expect(store.getSnapshot().bootstrap).toEqual({
      state: "hydrated",
      hydratedAt: "2026-03-31T12:34:56.000Z",
      version: 7,
    });
    expect(store.getSnapshot().querySystem.server).toEqual({
      configs: [{ config_id: "cfg-1", name: "白天配置", serverShape: "summary" }],
      capacitySummary: { modes: {} },
      runtimeStatus: { running: true, item_rows: [{ query_item_id: "item-1" }] },
    });
    expect(store.getSnapshot().purchaseSystem.server).toEqual({
      runtimeStatus: { running: false, accounts: [], item_rows: [] },
      uiPreferences: { selected_config_id: "cfg-1", updated_at: "2026-03-31T12:34:56.000Z" },
      runtimeSettings: { per_batch_ip_fanout_limit: 1, updated_at: null },
    });
    expect(store.getSnapshot().connection).toEqual({
      state: "connected",
      stale: false,
      lastSyncAt: "2026-03-31T12:35:00.000Z",
      lastEventVersion: 7,
      lastError: "",
    });
  });

  it("keeps existing ui and draft state when bootstrap fails and only marks the connection stale", async () => {
    const store = createAppRuntimeStore();
    const client = {
      getAppBootstrap: vi.fn().mockRejectedValue(new Error("network down")),
    };
    const manager = createRuntimeConnectionManager({
      client,
      now: () => "2026-03-31T12:40:00.000Z",
      store,
    });

    store.patchQueryUi({ selectedConfigId: "cfg-draft" });
    store.patchQueryDraft({
      currentConfig: { config_id: "cfg-draft", name: "本地草稿" },
      hasUnsavedChanges: true,
    });

    await expect(manager.bootstrap()).rejects.toThrow("network down");

    expect(store.getSnapshot().querySystem.ui).toEqual({ selectedConfigId: "cfg-draft" });
    expect(store.getSnapshot().querySystem.draft).toEqual({
      currentConfig: { config_id: "cfg-draft", name: "本地草稿" },
      hasUnsavedChanges: true,
    });
    expect(store.getSnapshot().connection).toEqual({
      state: "error",
      stale: true,
      lastSyncAt: null,
      lastEventVersion: 0,
      lastError: "network down",
    });
  });

  it("skips duplicate bootstrap requests once the store is already hydrated unless forced", async () => {
    const store = createAppRuntimeStore();
    const client = {
      getAppBootstrap: vi.fn().mockResolvedValue({
        version: 2,
        generated_at: "2026-03-31T13:00:00.000Z",
        query_system: {
          configs: [],
          capacitySummary: { modes: {} },
          runtimeStatus: { running: false, item_rows: [] },
        },
      }),
    };
    const manager = createRuntimeConnectionManager({
      client,
      now: () => "2026-03-31T13:00:05.000Z",
      store,
    });

    await manager.bootstrap();
    await manager.bootstrap();
    await manager.bootstrap({ force: true });

    expect(client.getAppBootstrap).toHaveBeenCalledTimes(2);
  });
});
