export function AccountContextMenu({ menu, onClose, onDelete }) {
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
          onDelete?.(menu.account);
          onClose?.();
        }}
      >
        删除账号
      </button>
    </div>
  );
}
