import { useEffect, useState } from "react";


const CUSTOM_VALUE = "__custom__";


function formatProxyLabel(proxy) {
  const auth = proxy.username
    ? `${proxy.username}${proxy.password ? `:${proxy.password}` : ""}@`
    : "";
  return `${proxy.name} — ${proxy.scheme}://${auth}${proxy.host}:${proxy.port}`;
}


function buildInitialSelect(account, proxies) {
  if (!account) {
    return "";
  }
  if (account.browser_proxy_mode === "pool" && account.browser_proxy_id) {
    const found = proxies.find((p) => p.proxy_id === account.browser_proxy_id);
    if (found) {
      return account.browser_proxy_id;
    }
  }
  if (account.browser_proxy_mode === "custom" && account.browser_proxy_url) {
    return CUSTOM_VALUE;
  }
  return "";
}


function buildInitialInput(account) {
  if (!account) {
    return "";
  }
  if (account.browser_proxy_mode === "custom") {
    return account.browser_proxy_url ?? "";
  }
  return "";
}


export function AccountBrowserProxyDialog({
  account,
  open,
  onClose,
  onSubmit,
  proxies = [],
}) {
  const [selectValue, setSelectValue] = useState("");
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (open && account) {
      setSelectValue(buildInitialSelect(account, proxies));
      setInputValue(buildInitialInput(account));
    }
  }, [account, open, proxies]);

  if (!open || !account) {
    return null;
  }

  function buildPayload() {
    if (!selectValue) {
      return { browser_proxy_mode: "direct", browser_proxy_url: null, browser_proxy_id: null };
    }
    if (selectValue === CUSTOM_VALUE) {
      const trimmed = inputValue.trim();
      const isDirect = !trimmed || trimmed.toLowerCase() === "direct";
      return {
        browser_proxy_mode: isDirect ? "direct" : "custom",
        browser_proxy_url: isDirect ? null : trimmed,
        browser_proxy_id: null,
      };
    }
    return { browser_proxy_mode: "pool", browser_proxy_url: null, browser_proxy_id: selectValue };
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
          await onSubmit?.(buildPayload());
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="browser-proxy-dialog-title">浏览器代理设置</h2>
            <p className="surface-subtitle">从代理池选择或自定义输入，选择「直连」则不使用代理。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="account-browser-proxy-select">浏览器代理</label>
            <select
              className="form-select"
              id="account-browser-proxy-select"
              value={selectValue}
              onChange={(e) => setSelectValue(e.target.value)}
            >
              <option value="">直连（不使用代理）</option>
              {proxies.map((p) => (
                <option key={p.proxy_id} value={p.proxy_id}>{formatProxyLabel(p)}</option>
              ))}
              <option value={CUSTOM_VALUE}>── 自定义输入 ──</option>
            </select>
            {selectValue === CUSTOM_VALUE && (
              <input
                className="form-input"
                placeholder="输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
                style={{ marginTop: 6 }}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
              />
            )}
            <span className="form-hint">
              这里只影响浏览器登录与浏览器查询的代理出口，不会同步改动 API 代理。
            </span>
            <span className="form-hint">
              已打开的浏览器窗口不会立即切到新代理；保存后需关闭旧窗口并重新打开，或重新登录后才会生效。
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
