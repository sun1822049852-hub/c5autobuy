export function AccountContextMenu({ menu, onClose, onDelete, onOpenOpenApiBindingPage, onSyncOpenApi }) {
  if (!menu) {
    return null;
  }

  return (
    <div
      className="context-menu"
      role="menu"
      style={{
        left: menu.position?.x ?? 24,
        top: menu.position?.y ?? 24,
      }}
    >
      <button
        className="context-menu__button"
        type="button"
        onClick={() => {
          onSyncOpenApi?.(menu.account);
          onClose?.();
        }}
      >
        重新同步 API 白名单
      </button>
      <button
        className="context-menu__button"
        type="button"
        onClick={() => {
          onOpenOpenApiBindingPage?.(menu.account);
          onClose?.();
        }}
      >
        打开 API 绑定页
      </button>
      <button
        className="context-menu__button"
        type="button"
        onClick={() => {
          onDelete?.(menu.account);
          onClose?.();
        }}
      >
        删除账号
      </button>
    </div>
  );
}
