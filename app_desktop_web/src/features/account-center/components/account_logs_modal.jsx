import { FloatingRuntimeModal } from "../../purchase-system/components/floating_runtime_modal.jsx";


export function AccountLogsModal({
  entries,
  isOpen,
  onClose,
  onPositionChange,
  onSizeChange,
  position,
  size,
}) {
  function renderMeta(meta) {
    if (!meta || (Array.isArray(meta) && meta.length === 0)) {
      return null;
    }

    const lines = Array.isArray(meta) ? meta : [meta];
    return (
      <div className="account-logs__item-meta">
        {lines.map((line, index) => (
          <div key={`${line}-${index}`} className="account-logs__item-meta-line">{line}</div>
        ))}
      </div>
    );
  }

  return (
    <FloatingRuntimeModal
      isOpen={isOpen}
      onClose={onClose}
      onPositionChange={onPositionChange}
      onSizeChange={onSizeChange}
      position={position}
      size={size}
      title="日志"
    >
      <section className="account-logs">
        {entries.length ? (
          <div className="account-logs__list">
            {entries.map((entry) => (
              <article key={entry.id} className="account-logs__item">
                <div className="account-logs__item-title">{entry.title}</div>
                <div className="account-logs__item-message">{entry.message}</div>
                {renderMeta(entry.meta)}
              </article>
            ))}
          </div>
        ) : (
          <div className="account-logs__empty">当前没有日志</div>
        )}
      </section>
    </FloatingRuntimeModal>
  );
}
