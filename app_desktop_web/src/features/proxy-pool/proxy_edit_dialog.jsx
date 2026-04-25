import { useEffect, useState } from "react";


const SCHEME_OPTIONS = ["http", "https", "socks5"];

const EMPTY_FORM = { name: "", scheme: "http", host: "", port: "", username: "", password: "" };


export function ProxyEditDialog({ open, proxy, onClose, onSubmit, onTest }) {
  const isEdit = Boolean(proxy?.proxy_id);
  const [form, setForm] = useState(EMPTY_FORM);
  const [testResult, setTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(proxy
        ? {
            name: proxy.name ?? "",
            scheme: proxy.scheme ?? "http",
            host: proxy.host ?? "",
            port: proxy.port ?? "",
            username: proxy.username ?? "",
            password: proxy.password ?? "",
          }
        : { ...EMPTY_FORM });
      setTestResult(null);
    }
  }, [open, proxy]);

  if (!open) {
    return null;
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleTest() {
    setIsTesting(true);
    setTestResult(null);
    try {
      if (isEdit && onTest) {
        const result = await onTest(proxy.proxy_id);
        setTestResult(result);
      } else {
        setTestResult({ error: "请先保存后再测试" });
      }
    } catch (error) {
      setTestResult({ reachable: false, error: error.message || String(error) });
    } finally {
      setIsTesting(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    try {
      await onSubmit?.({
        name: form.name.trim(),
        scheme: form.scheme,
        host: form.host.trim(),
        port: form.port.trim(),
        username: form.username.trim() || null,
        password: form.password.trim() || null,
      });
    } finally {
      setIsSaving(false);
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
        aria-labelledby="proxy-edit-dialog-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={handleSubmit}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="proxy-edit-dialog-title">
              {isEdit ? "编辑代理" : "新增代理"}
            </h2>
            <p className="surface-subtitle">填写代理服务器的结构化信息。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">名称</span>
            <input
              className="form-input"
              placeholder="如：日本1号"
              required
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
            />
          </label>

          <label className="form-field">
            <span className="form-label">协议</span>
            <select
              className="form-select"
              value={form.scheme}
              onChange={(e) => updateField("scheme", e.target.value)}
            >
              {SCHEME_OPTIONS.map((s) => (
                <option key={s} value={s}>{s.toUpperCase()}</option>
              ))}
            </select>
          </label>

          <label className="form-field">
            <span className="form-label">地址</span>
            <input
              className="form-input"
              placeholder="如：jp1.proxy.com"
              required
              value={form.host}
              onChange={(e) => updateField("host", e.target.value)}
            />
          </label>

          <label className="form-field">
            <span className="form-label">端口</span>
            <input
              className="form-input"
              placeholder="如：9000"
              required
              value={form.port}
              onChange={(e) => updateField("port", e.target.value)}
            />
          </label>

          <label className="form-field">
            <span className="form-label">用户名（选填）</span>
            <input
              className="form-input"
              placeholder="留空则无认证"
              value={form.username}
              onChange={(e) => updateField("username", e.target.value)}
            />
          </label>

          <label className="form-field">
            <span className="form-label">密码（选填）</span>
            <input
              className="form-input"
              placeholder="留空则无认证"
              type="text"
              value={form.password}
              onChange={(e) => updateField("password", e.target.value)}
            />
          </label>

          {testResult && (
            <div className="form-field">
              <span className="form-label">测试结果</span>
              <div className="form-input" role="note" style={{
                color: testResult.reachable ? "var(--color-success, #22c55e)" : "var(--color-danger, #ef4444)",
              }}>
                {testResult.reachable
                  ? `可达 · ${testResult.latency_ms}ms · 出口IP: ${testResult.public_ip}`
                  : `不可达 · ${testResult.error || "未知错误"}`}
              </div>
            </div>
          )}
        </div>

        <div className="surface-actions">
          {isEdit && (
            <button
              className="ghost-button"
              disabled={isTesting}
              type="button"
              onClick={handleTest}
            >
              {isTesting ? "测试中..." : "测试连接"}
            </button>
          )}
          <button className="accent-button" disabled={isSaving} type="submit">
            {isSaving ? "保存中..." : "保存"}
          </button>
        </div>
      </form>
    </div>
  );
}
