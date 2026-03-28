import { useEffect, useState } from "react";


export function AccountProxyDialog({
  account,
  open,
  onClose,
  onOpenBindingPage,
  onSubmit,
}) {
  const [apiProxyInput, setApiProxyInput] = useState("");

  useEffect(() => {
    if (open && account) {
      setApiProxyInput(account.api_proxy_mode === "direct" ? "" : (account.api_proxy_url ?? ""));
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
          const normalizedApiProxyInput = apiProxyInput.trim();
          await onSubmit?.({
            api_proxy_mode: normalizedApiProxyInput ? "custom" : "direct",
            api_proxy_url: normalizedApiProxyInput || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="proxy-dialog-title">API IP 设置</h2>
            <p className="surface-subtitle">上半区用于查看并添加 API 白名单，下半区用于修改 API 代理出口。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="account-api-whitelist-ip">白名单 IP</label>
            <div className="form-input" id="account-api-whitelist-ip" role="note">
              {account.api_ip_allow_list || "未获取白名单"}
            </div>
            <span className="form-hint">以已登录浏览器打开绑定页后显示的白名单 IP 为准。当前出口 IP：{account.api_public_ip || "未获取IP"}</span>
            <div className="surface-actions">
              <button className="ghost-button" type="button" onClick={() => onOpenBindingPage?.(account)}>
                添加白名单
              </button>
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="account-api-proxy-input">API代理</label>
            <input
              aria-describedby="account-api-proxy-hint"
              className="form-input"
              id="account-api-proxy-input"
              placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={apiProxyInput}
              onChange={(event) => setApiProxyInput(event.target.value)}
            />
            <span className="form-hint" id="account-api-proxy-hint">用于 API 查询与白名单匹配检测；保存后会自动重新同步白名单状态。</span>
          </div>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit">保存</button>
        </div>
      </form>
    </div>
  );
}
