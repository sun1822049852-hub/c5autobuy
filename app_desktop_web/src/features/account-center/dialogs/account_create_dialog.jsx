import { useEffect, useState } from "react";


const CUSTOM_VALUE = "__custom__";

const DEFAULT_FORM = {
  remark_name: "",
  browser_proxy_select: "",
  browser_proxy_input: "",
  api_proxy_select: "",
  api_proxy_input: "",
};


function formatProxyLabel(proxy) {
  const auth = proxy.username ? `${proxy.username}:***@` : "";
  return `${proxy.name} — ${proxy.scheme}://${auth}${proxy.host}:${proxy.port}`;
}


function ProxySelectField({ id, label, hint, proxies, selectValue, inputValue, onSelectChange, onInputChange }) {
  const showCustomInput = selectValue === CUSTOM_VALUE;

  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>{label}</label>
      <select
        className="form-select"
        id={id}
        value={selectValue}
        onChange={(e) => onSelectChange(e.target.value)}
      >
        <option value="">直连（不使用代理）</option>
        {proxies.map((p) => (
          <option key={p.proxy_id} value={p.proxy_id}>{formatProxyLabel(p)}</option>
        ))}
        <option value={CUSTOM_VALUE}>── 自定义输入 ──</option>
      </select>
      {showCustomInput && (
        <input
          className="form-input"
          placeholder="127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
          style={{ marginTop: 6 }}
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
        />
      )}
      {hint && <span className="form-hint">{hint}</span>}
    </div>
  );
}


export function AccountCreateDialog({ open, onClose, onSubmit, proxies = [] }) {
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

  function buildProxyPayload(selectValue, inputValue) {
    if (!selectValue) {
      return { mode: "direct", url: null, proxy_id: null };
    }
    if (selectValue === CUSTOM_VALUE) {
      const trimmed = inputValue.trim();
      return { mode: trimmed ? "custom" : "direct", url: trimmed || null, proxy_id: null };
    }
    // Pool selection — backend resolves URL from proxy_id
    return { mode: "pool", url: null, proxy_id: selectValue };
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
          const browser = buildProxyPayload(form.browser_proxy_select, form.browser_proxy_input);
          const api = buildProxyPayload(form.api_proxy_select, form.api_proxy_input);
          await onSubmit?.({
            api_key: null,
            browser_proxy_mode: browser.mode,
            browser_proxy_url: browser.url,
            browser_proxy_id: browser.proxy_id,
            api_proxy_mode: api.mode,
            api_proxy_url: api.url,
            api_proxy_id: api.proxy_id,
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

          <ProxySelectField
            id="create-account-browser-proxy"
            label="浏览器代理"
            hint="登录浏览器使用；改动后通常需要重新登录。"
            proxies={proxies}
            selectValue={form.browser_proxy_select}
            inputValue={form.browser_proxy_input}
            onSelectChange={(value) => {
              setForm((current) => {
                const shouldPrefillApi = !apiProxyTouched || current.api_proxy_select === current.browser_proxy_select;
                return {
                  ...current,
                  browser_proxy_select: value,
                  api_proxy_select: shouldPrefillApi ? value : current.api_proxy_select,
                };
              });
            }}
            onInputChange={(value) => {
              setForm((current) => {
                const shouldPrefillApi = !apiProxyTouched || current.api_proxy_input === current.browser_proxy_input;
                return {
                  ...current,
                  browser_proxy_input: value,
                  api_proxy_input: shouldPrefillApi ? value : current.api_proxy_input,
                };
              });
            }}
          />

          <ProxySelectField
            id="create-account-api-proxy"
            label="API代理"
            hint="API 查询使用；支持动态切换，系统会自动检查当前出口 IP 是否在白名单内。"
            proxies={proxies}
            selectValue={form.api_proxy_select}
            inputValue={form.api_proxy_input}
            onSelectChange={(value) => {
              setApiProxyTouched(true);
              setForm((current) => ({ ...current, api_proxy_select: value }));
            }}
            onInputChange={(value) => {
              setApiProxyTouched(true);
              setForm((current) => ({ ...current, api_proxy_input: value }));
            }}
          />
        </div>

        <div className="surface-actions">
          <button className="ghost-button" data-action="save" type="submit">保存</button>
          <button className="accent-button" data-action="save-and-login" type="submit">保存并登录</button>
        </div>
      </form>
    </div>
  );
}
