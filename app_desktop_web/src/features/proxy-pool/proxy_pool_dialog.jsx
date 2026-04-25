import { useState } from "react";

import { ProxyBatchImportDialog } from "./proxy_batch_import_dialog.jsx";
import { ProxyEditDialog } from "./proxy_edit_dialog.jsx";


function formatProxyUrl(proxy) {
  const auth = proxy.username
    ? `${proxy.username}${proxy.password ? `:${proxy.password}` : ""}@`
    : "";
  return `${proxy.scheme}://${auth}${proxy.host}:${proxy.port}`;
}


export function ProxyPoolDialog({
  open,
  proxies,
  onClose,
  onCreateProxy,
  onUpdateProxy,
  onDeleteProxy,
  onTestProxy,
  onBatchImport,
}) {
  const [editDialogProxy, setEditDialogProxy] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [batchImportOpen, setBatchImportOpen] = useState(false);
  const [testResults, setTestResults] = useState({});
  const [testingIds, setTestingIds] = useState({});

  if (!open) {
    return null;
  }

  function openCreateDialog() {
    setEditDialogProxy(null);
    setEditDialogOpen(true);
  }

  function openEditDialog(proxy) {
    setEditDialogProxy(proxy);
    setEditDialogOpen(true);
  }

  async function handleEditSubmit(payload) {
    if (editDialogProxy?.proxy_id) {
      await onUpdateProxy?.(editDialogProxy.proxy_id, payload);
    } else {
      await onCreateProxy?.(payload);
    }
    setEditDialogOpen(false);
    setEditDialogProxy(null);
  }

  async function handleTest(proxyId) {
    setTestingIds((prev) => ({ ...prev, [proxyId]: true }));
    try {
      const result = await onTestProxy?.(proxyId);
      setTestResults((prev) => ({ ...prev, [proxyId]: result }));
      return result;
    } catch (error) {
      const result = { reachable: false, error: error.message || String(error) };
      setTestResults((prev) => ({ ...prev, [proxyId]: result }));
      return result;
    } finally {
      setTestingIds((prev) => ({ ...prev, [proxyId]: false }));
    }
  }

  async function handleDelete(proxyId) {
    if (!window.confirm("确定删除此代理？使用该代理的账号将自动切换为直连模式。")) {
      return;
    }
    await onDeleteProxy?.(proxyId);
  }

  async function handleBatchImport(payload) {
    await onBatchImport?.(payload);
    setBatchImportOpen(false);
  }

  return (
    <div
      className="surface-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose?.();
        }
      }}
    >
      <div
        aria-labelledby="proxy-pool-dialog-title"
        className="dialog-surface"
        role="dialog"
        style={{ maxWidth: 720, width: "90vw" }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="proxy-pool-dialog-title">代理管理</h2>
            <p className="surface-subtitle">管理全局代理池，账号可从中选择代理。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
        </div>

        <div style={{ display: "flex", gap: 8, padding: "0 16px 12px" }}>
          <button className="accent-button" type="button" onClick={openCreateDialog}>新增代理</button>
          <button className="ghost-button" type="button" onClick={() => setBatchImportOpen(true)}>批量导入</button>
        </div>

        <div style={{ padding: "0 16px 16px", overflowY: "auto", maxHeight: "60vh" }}>
          {proxies.length === 0 ? (
            <p style={{ color: "var(--color-text-secondary, #888)", textAlign: "center", padding: 24 }}>
              暂无代理，点击「新增代理」或「批量导入」添加。
            </p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--color-border, #333)" }}>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>名称</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>地址</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>用户名</th>
                  <th style={{ textAlign: "left", padding: "6px 8px" }}>状态</th>
                  <th style={{ textAlign: "right", padding: "6px 8px" }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {proxies.map((proxy) => {
                  const result = testResults[proxy.proxy_id];
                  const isTesting = testingIds[proxy.proxy_id];
                  return (
                    <tr key={proxy.proxy_id} style={{ borderBottom: "1px solid var(--color-border, #222)" }}>
                      <td style={{ padding: "6px 8px" }}>{proxy.name}</td>
                      <td style={{ padding: "6px 8px", fontFamily: "monospace", fontSize: 12 }}>
                        {formatProxyUrl(proxy)}
                      </td>
                      <td style={{ padding: "6px 8px" }}>{proxy.username || "—"}</td>
                      <td style={{ padding: "6px 8px", fontSize: 12 }}>
                        {isTesting ? (
                          <span style={{ color: "var(--color-text-secondary, #888)" }}>测试中...</span>
                        ) : result ? (
                          result.reachable ? (
                            <span style={{ color: "var(--color-success, #22c55e)" }}>
                              可达 · {result.latency_ms}ms
                            </span>
                          ) : (
                            <span style={{ color: "var(--color-danger, #ef4444)" }}>
                              不可达
                            </span>
                          )
                        ) : (
                          <span style={{ color: "var(--color-text-secondary, #888)" }}>未测试</span>
                        )}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                        <button
                          className="ghost-button"
                          style={{ fontSize: 12, padding: "2px 6px" }}
                          type="button"
                          onClick={() => openEditDialog(proxy)}
                        >
                          编辑
                        </button>
                        <button
                          className="ghost-button"
                          disabled={isTesting}
                          style={{ fontSize: 12, padding: "2px 6px" }}
                          type="button"
                          onClick={() => handleTest(proxy.proxy_id)}
                        >
                          测试
                        </button>
                        <button
                          className="ghost-button"
                          style={{ fontSize: 12, padding: "2px 6px", color: "var(--color-danger, #ef4444)" }}
                          type="button"
                          onClick={() => handleDelete(proxy.proxy_id)}
                        >
                          删除
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <ProxyEditDialog
        open={editDialogOpen}
        proxy={editDialogProxy}
        onClose={() => {
          setEditDialogOpen(false);
          setEditDialogProxy(null);
        }}
        onSubmit={handleEditSubmit}
        onTest={handleTest}
      />

      <ProxyBatchImportDialog
        open={batchImportOpen}
        onClose={() => setBatchImportOpen(false)}
        onSubmit={handleBatchImport}
      />
    </div>
  );
}
