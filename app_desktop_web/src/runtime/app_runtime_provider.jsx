import { createContext, useRef } from "react";

import { createAppRuntimeStore } from "./app_runtime_store.js";


export const AppRuntimeContext = createContext(null);


export function AppRuntimeProvider({ children, store }) {
  const fallbackStoreRef = useRef(null);

  if (!fallbackStoreRef.current) {
    fallbackStoreRef.current = createAppRuntimeStore();
  }

  return (
    <AppRuntimeContext.Provider value={store ?? fallbackStoreRef.current}>
      {children}
    </AppRuntimeContext.Provider>
  );
}
