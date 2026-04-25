import { useEffect, useState } from "react";


export function ProxyBatchImportDialog({ open, onClose, onSubmit }) {
  const [text, setText] = useState("");
  const [defaultScheme, setDefaultScheme] = useState("http");
  const [isImporting, setIsImporting] = useState(false);

  useEffect(() => {
    if (open) {
      setText("");
      setDefaultScheme("http");
    }
  }, [open]);

  if (!open) {
    return null;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!text.trim()) {
      return;
    }
    setIsImporting(true);
    try {
      await onSubmit?.({ text: text.trim(), default_scheme: defaultScheme });
      setText("");
    } finally {
      setIsImporting(false);
    }
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
        aria-labelledby="proxy-batch-import-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={handleSubmit}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="proxy-batch-import-title">批量导入代理</h2>
            <p className="surface-subtitle">一行一个，支持多种格式。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <div className="form-field">
            <label className="form-label" htmlFor="proxy-batch-text">代理列表</label>
            <textarea
              className="form-input"
              id="proxy-batch-text"
              placeholder={"host:port\nhost:port:user:pass\nsocks5://user:pass@host:port"}
              rows={8}
              style={{ resize: "vertical", fontFamily: "monospace" }}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <span className="form-hint">
              支持格式：host:port、host:port:user:pass、socks5://user:pass@host:port
            </span>
          </div>

          <label className="form-field">
            <span className="form-label">默认协议</span>
            <select
              className="form-select"
              value={defaultScheme}
              onChange={(e) => setDefaultScheme(e.target.value)}
            >
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
              <option value="socks5">SOCKS5</option>
            </select>
            <span className="form-hint">当行内未指定协议时使用此默认值。</span>
          </label>
        </div>

        <div className="surface-actions">
          <button className="accent-button" disabled={isImporting || !text.trim()} type="submit">
            {isImporting ? "导入中..." : "导入"}
          </button>
        </div>
      </form>
    </div>
  );
}
