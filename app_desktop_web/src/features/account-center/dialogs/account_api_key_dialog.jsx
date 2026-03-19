import { useEffect, useState } from "react";


export function AccountApiKeyDialog({ account, open, onClose, onSubmit }) {
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    if (open) {
      setApiKey(account?.api_key ?? "");
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
        aria-labelledby="api-key-dialog-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={async (event) => {
          event.preventDefault();
          await onSubmit?.({
            api_key: apiKey.trim() || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="api-key-dialog-title">修改 API Key</h2>
            <p className="surface-subtitle">支持补录、覆盖或清空当前账号的 API Key。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">API Key</span>
            <input
              className="form-input"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
        </div>

        <div className="surface-actions">
          <button className="accent-button" type="submit">保存</button>
        </div>
      </form>
    </div>
  );
}
