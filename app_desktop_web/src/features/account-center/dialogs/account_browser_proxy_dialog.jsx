import { useEffect, useState } from "react";


function buildInitialInput(account) {
  if (!account) {
    return "";
  }
  return account.browser_proxy_mode === "direct" ? "direct" : (account.browser_proxy_url ?? "");
}


export function AccountBrowserProxyDialog({
  account,
  open,
  onClose,
  onSubmit,
}) {
  const [browserProxyInput, setBrowserProxyInput] = useState("");

  useEffect(() => {
    if (open && account) {
      setBrowserProxyInput(buildInitialInput(account));
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
        aria-labelledby="browser-proxy-dialog-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={async (event) => {
          event.preventDefault();
          const normalizedInput = browserProxyInput.trim();
          const isDirect = !normalizedInput || normalizedInput.toLowerCase() === "direct";
          await onSubmit?.({
            browser_proxy_mode: isDirect ? "direct" : "custom",
            browser_proxy_url: isDirect ? null : normalizedInput,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="browser-proxy-dialog-title">浏览器代理设置</h2>
            <p className="surface-subtitle">输入代理地址即可切换浏览器出口，输入 `direct` 或留空则回到直连。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="account-browser-proxy-input">浏览器代理</label>
            <input
              aria-describedby="account-browser-proxy-hint"
              className="form-input"
              id="account-browser-proxy-input"
              placeholder="输入 direct 为直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={browserProxyInput}
              onChange={(event) => setBrowserProxyInput(event.target.value)}
            />
            <span className="form-hint" id="account-browser-proxy-hint">
              这里只影响浏览器登录与浏览器查询的代理出口，不会同步改动 API 代理。
            </span>
          </div>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit">保存</button>
        </div>
      </form>
    </div>
  );
}
