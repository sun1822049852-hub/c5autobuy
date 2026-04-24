import { useCallback, useEffect, useState } from "react";


export function useProxyPool({ client }) {
  const [proxies, setProxies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await client.listProxies();
      setProxies(list);
      return list;
    } catch {
      return proxies;
    } finally {
      setIsLoading(false);
    }
  }, [client]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createProxy = useCallback(async (payload) => {
    const entry = await client.createProxy(payload);
    await refresh();
    return entry;
  }, [client, refresh]);

  const updateProxy = useCallback(async (proxyId, payload) => {
    const entry = await client.updateProxy(proxyId, payload);
    await refresh();
    return entry;
  }, [client, refresh]);

  const deleteProxy = useCallback(async (proxyId) => {
    await client.deleteProxy(proxyId);
    await refresh();
  }, [client, refresh]);

  const testProxy = useCallback(async (proxyId) => {
    return client.testProxy(proxyId);
  }, [client]);

  const batchImport = useCallback(async (payload) => {
    const entries = await client.batchImportProxies(payload);
    await refresh();
    return entries;
  }, [client, refresh]);

  return {
    proxies,
    isLoading,
    refresh,
    createProxy,
    updateProxy,
    deleteProxy,
    testProxy,
    batchImport,
  };
}
