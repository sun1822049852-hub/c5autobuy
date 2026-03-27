import { useEffect, useState } from "react";


const DEFAULT_FORM = {
  remark_name: "",
  browser_proxy_input: "",
  api_proxy_input: "",
};


export function AccountCreateDialog({ open, onClose, onSubmit }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [apiProxyTouched, setApiProxyTouched] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(DEFAULT_FORM);
      setApiProxyTouched(false);
    }
  }, [open]);

  if (!open) {
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
        aria-labelledby="create-account-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={async (event) => {
          event.preventDefault();
          const browserProxyInput = form.browser_proxy_input.trim();
          const apiProxyInput = form.api_proxy_input.trim();
          await onSubmit?.({
            api_key: null,
            browser_proxy_mode: browserProxyInput ? "custom" : "direct",
            browser_proxy_url: browserProxyInput || null,
            api_proxy_mode: apiProxyInput ? "custom" : "direct",
            api_proxy_url: apiProxyInput || null,
            remark_name: form.remark_name.trim() || null,
          }, {
            startLoginAfterCreate: event.nativeEvent.submitter?.dataset.action === "save-and-login",
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="create-account-title">添加账号</h2>
            <p className="surface-subtitle">API Key 改为后续手动填写；代理留空即直连，也可以在这里直接保存并登录。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">备注</span>
            <input
              className="form-input"
              name="remark_name"
              value={form.remark_name}
              onChange={(event) => setForm((current) => ({
                ...current,
                remark_name: event.target.value,
              }))}
            />
          </label>

          <div className="form-field">
            <label className="form-label" htmlFor="create-account-browser-proxy-input">浏览器代理</label>
            <input
              aria-describedby="create-account-browser-proxy-hint"
              className="form-input"
              id="create-account-browser-proxy-input"
              name="browser_proxy_input"
              placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={form.browser_proxy_input}
              onChange={(event) => setForm((current) => {
                const nextBrowserProxyInput = event.target.value;
                const shouldPrefillApi = !apiProxyTouched || current.api_proxy_input === current.browser_proxy_input;
                return {
                  ...current,
                  browser_proxy_input: nextBrowserProxyInput,
                  api_proxy_input: shouldPrefillApi ? nextBrowserProxyInput : current.api_proxy_input,
                };
              })}
            />
            <span className="form-hint" id="create-account-browser-proxy-hint">登录浏览器使用；改动后通常需要重新登录。</span>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="create-account-api-proxy-input">API代理</label>
            <input
              aria-describedby="create-account-api-proxy-hint"
              className="form-input"
              id="create-account-api-proxy-input"
              name="api_proxy_input"
              placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={form.api_proxy_input}
              onChange={(event) => {
                setApiProxyTouched(true);
                setForm((current) => ({
                  ...current,
                  api_proxy_input: event.target.value,
                }));
              }}
            />
            <span className="form-hint" id="create-account-api-proxy-hint">API 查询使用；支持动态切换，系统会自动检查当前出口 IP 是否在白名单内。</span>
          </div>
        </div>

        <div className="surface-actions">
          <button className="ghost-button" data-action="save" type="submit">保存</button>
          <button className="accent-button" data-action="save-and-login" type="submit">保存并登录</button>
        </div>
      </form>
    </div>
  );
}
