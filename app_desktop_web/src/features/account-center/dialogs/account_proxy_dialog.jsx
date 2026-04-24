import { useEffect, useState } from "react";


const CUSTOM_VALUE = "__custom__";


function formatProxyLabel(proxy) {
  const auth = proxy.username ? `${proxy.username}:***@` : "";
  return `${proxy.name} — ${proxy.scheme}://${auth}${proxy.host}:${proxy.port}`;
}


function buildInitialSelect(account, proxies) {
  if (!account) {
    return "";
  }
  if (account.api_proxy_mode === "pool" && account.api_proxy_id) {
    const found = proxies.find((p) => p.proxy_id === account.api_proxy_id);
    if (found) {
      return account.api_proxy_id;
    }
  }
  if (account.api_proxy_mode === "custom" && account.api_proxy_url) {
    return CUSTOM_VALUE;
  }
  return "";
}


function buildInitialInput(account) {
  if (!account) {
    return "";
  }
  if (account.api_proxy_mode === "custom") {
    return account.api_proxy_url ?? "";
  }
  return "";
}


export function AccountProxyDialog({
  account,
  open,
  isOpeningBindingPage = false,
  onClose,
  onOpenBindingPage,
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
      return { api_proxy_mode: "direct", api_proxy_url: null, api_proxy_id: null };
    }
    if (selectValue === CUSTOM_VALUE) {
      const trimmed = inputValue.trim();
      const isDirect = !trimmed || trimmed.toLowerCase() === "direct";
      return {
        api_proxy_mode: isDirect ? "direct" : "custom",
        api_proxy_url: isDirect ? null : trimmed,
        api_proxy_id: null,
      };
    }
    return { api_proxy_mode: "pool", api_proxy_url: null, api_proxy_id: selectValue };
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
          await onSubmit?.(buildPayload());
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
              <button
                className="ghost-button"
                disabled={isOpeningBindingPage}
                type="button"
                onClick={() => onOpenBindingPage?.(account)}
              >
                {isOpeningBindingPage ? "正在打开..." : "添加白名单"}
              </button>
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="account-api-proxy-select">API代理</label>
            <select
              className="form-input"
              id="account-api-proxy-select"
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
                placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
                style={{ marginTop: 6 }}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
              />
            )}
            <span className="form-hint">用于 API 查询与白名单匹配检测；保存后会自动重新同步白名单状态。</span>
          </div>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit">保存</button>
        </div>
      </form>
    </div>
  );
}
