import { useEffect, useState } from "react";


export function AccountRemarkDialog({ account, open, onClose, onSubmit }) {
  const [remarkName, setRemarkName] = useState("");

  useEffect(() => {
    if (open) {
      setRemarkName(account?.remark_name ?? account?.display_name ?? "");
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
        aria-labelledby="remark-dialog-title"
        className="dialog-surface"
        role="dialog"
        onSubmit={async (event) => {
          event.preventDefault();
          await onSubmit?.({
            remark_name: remarkName.trim() || null,
          });
        }}
      >
        <div className="surface-header">
          <div>
            <h2 className="surface-title" id="remark-dialog-title">修改备注</h2>
            <p className="surface-subtitle">C5 昵称这一列现在承载备注编辑入口。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">备注</span>
            <input
              className="form-input"
              value={remarkName}
              onChange={(event) => setRemarkName(event.target.value)}
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
