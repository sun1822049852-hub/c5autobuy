import { useEffect, useState } from "react";


const DEFAULT_FORM = {
  remark_name: "",
  proxy_input: "",
};


export function AccountCreateDialog({ open, onClose, onSubmit }) {
  const [form, setForm] = useState(DEFAULT_FORM);

  useEffect(() => {
    if (open) {
      setForm(DEFAULT_FORM);
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
          const proxyInput = form.proxy_input.trim();
          await onSubmit?.({
            api_key: null,
            proxy_mode: proxyInput ? "custom" : "direct",
            proxy_url: proxyInput || null,
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
            <label className="form-label" htmlFor="create-account-proxy-input">代理</label>
            <input
              aria-describedby="create-account-proxy-hint"
              className="form-input"
              id="create-account-proxy-input"
              name="proxy_input"
              placeholder="留空直连，或输入 127.0.0.1:9000 / user:pass@127.0.0.1:9000 / socks5://..."
              value={form.proxy_input}
              onChange={(event) => setForm((current) => ({
                ...current,
                proxy_input: event.target.value,
              }))}
            />
            <span className="form-hint" id="create-account-proxy-hint">留空即直连；支持 host:port、user:pass@host:port、完整 http(s):// 与 socks5://。</span>
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
