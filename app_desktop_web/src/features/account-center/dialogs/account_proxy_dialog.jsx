import { useEffect, useState } from "react";


export function AccountProxyDialog({ account, open, onClose, onSubmit }) {
  const [proxyInput, setProxyInput] = useState("");

  useEffect(() => {
    if (open && account) {
      setProxyInput(account.proxy_mode === "direct" ? "" : (account.proxy_url ?? ""));
    }
  }, [account, open]);

  if (!open || !account) {
    return null;
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
      <form
        aria-labelledby="proxy-dialog-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={async (event) => {
          event.preventDefault();
          const normalizedProxyInput = proxyInput.trim();
          await onSubmit?.({
            proxy_mode: normalizedProxyInput ? "custom" : "direct",
            proxy_url: normalizedProxyInput || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="proxy-dialog-title">修改代理</h2>
            <p className="surface-subtitle">留空即直连；支持 host:port、user:pass@host:port、完整 URL。改动后会自动拉起登录抽屉。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="account-proxy-input">代理</label>
            <input
              aria-describedby="account-proxy-hint"
              className="form-input"
              id="account-proxy-input"
              placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={proxyInput}
              onChange={(event) => setProxyInput(event.target.value)}
            />
            <span className="form-hint" id="account-proxy-hint">如果只填 host:port 或 user:pass@host:port，后端会自动补成 http://。</span>
          </div>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit">保存</button>
        </div>
      </form>
    </div>
  );
}
