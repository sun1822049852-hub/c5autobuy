function resolveAccountName(account) {
  if (!account) {
    return "";
  }
  return account.display_name || account.remark_name || account.c5_nick_name || account.default_name || account.account_id;
}


export function AccountDeleteDialog({
  account,
  isDeleting = false,
  open = false,
  onClose,
  onConfirm,
}) {
  if (!open || !account) {
    return null;
  }

  return (
    <div
      className="surface-backdrop"
      role="presentation"
      onClick={(event) => {
        if (isDeleting) {
          return;
        }
        if (event.target === event.currentTarget) {
          onClose?.();
        }
      }}
    >
      <section aria-label="删除账号" className="dialog-surface account-delete-dialog" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">删除账号</h2>
          </div>
        </div>

        <div className="account-delete-dialog__name">{resolveAccountName(account)}</div>

        <div className="surface-actions">
          <button className="ghost-button" type="button" disabled={isDeleting} onClick={onClose}>取消</button>
          <button className="accent-button" type="button" disabled={isDeleting} onClick={onConfirm}>
            {isDeleting ? "删除中..." : "确认删除"}
          </button>
        </div>
      </section>
    </div>
  );
}
