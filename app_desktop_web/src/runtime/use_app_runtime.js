import { useCallback, useContext, useSyncExternalStore } from "react";

import { AppRuntimeContext } from "./app_runtime_provider.jsx";


function useRequiredAppRuntimeStore() {
  const store = useContext(AppRuntimeContext);

  if (!store) {
    throw new Error("useAppRuntime* hooks must be used within AppRuntimeProvider.");
  }

  return store;
}


function useAppRuntimeSelector(selector) {
  const store = useRequiredAppRuntimeStore();

  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.getSnapshot()),
    () => selector(store.getSnapshot()),
  );
}


export function useBootstrapRuntime() {
  return useAppRuntimeSelector((snapshot) => snapshot.bootstrap);
}


export function useConnectionRuntime() {
  return useAppRuntimeSelector((snapshot) => snapshot.connection);
}


export function useProgramAccess() {
  return useAppRuntimeSelector((snapshot) => snapshot.programAccess);
}


export function useQuerySystemServer() {
  return useAppRuntimeSelector((snapshot) => snapshot.querySystem.server);
}


export function useQuerySystemServerHydrated() {
  return useAppRuntimeSelector((snapshot) => snapshot.querySystem.serverHydrated);
}


export function useQuerySystemUi() {
  return useAppRuntimeSelector((snapshot) => snapshot.querySystem.ui);
}


export function useQuerySystemDraft() {
  return useAppRuntimeSelector((snapshot) => snapshot.querySystem.draft);
}


export function usePatchQuerySystemUi() {
  const store = useRequiredAppRuntimeStore();

  return store.patchQueryUi;
}


export function usePatchQuerySystemDraft() {
  const store = useRequiredAppRuntimeStore();

  return store.patchQueryDraft;
}


export function useApplyQuerySystemServer() {
  const store = useRequiredAppRuntimeStore();

  return useCallback((serverPatch = {}) => store.applyQuerySystemServer(serverPatch), [store]);
}


export function usePurchaseSystemServer() {
  return useAppRuntimeSelector((snapshot) => snapshot.purchaseSystem.server);
}


export function usePurchaseSystemServerHydrated() {
  return useAppRuntimeSelector((snapshot) => snapshot.purchaseSystem.serverHydrated);
}


export function usePurchaseSystemUi() {
  return useAppRuntimeSelector((snapshot) => snapshot.purchaseSystem.ui);
}


export function usePurchaseSystemDraft() {
  return useAppRuntimeSelector((snapshot) => snapshot.purchaseSystem.draft);
}


export function usePatchPurchaseSystemUi() {
  const store = useRequiredAppRuntimeStore();

  return store.patchPurchaseUi;
}


export function usePatchPurchaseSystemDraft() {
  const store = useRequiredAppRuntimeStore();

  return store.patchPurchaseDraft;
}


export function useApplyPurchaseSystemServer() {
  const store = useRequiredAppRuntimeStore();

  return useCallback((serverPatch = {}) => store.applyPurchaseSystemServer(serverPatch), [store]);
}
