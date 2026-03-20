export function PurchaseConfigSelectorDialog({
  actionLabel,
  configs,
  isOpen,
  isSubmitting,
  onClose,
  onConfirm,
  onSelect,
  selectedConfigId,
}) {
  if (!isOpen) {
    return null;
  }

  const hasConfigs = configs.length > 0;

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
      <section aria-label="选择查询配置" className="dialog-surface purchase-config-dialog" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">选择查询配置</h2>
            <p className="surface-subtitle">购买页负责绑定和切换运行配置，查询页只保留配置编辑与保存。</p>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
        </div>

        {hasConfigs ? (
          <div className="purchase-config-dialog__list">
            {configs.map((config) => (
              <button
                key={config.config_id}
                aria-pressed={selectedConfigId === config.config_id}
                className={`purchase-config-dialog__item${selectedConfigId === config.config_id ? " is-selected" : ""}`}
                type="button"
                onClick={() => {
                  onSelect?.(config.config_id);
                }}
              >
                <div className="purchase-config-dialog__item-name">{config.name}</div>
                <div className="purchase-config-dialog__item-description">
                  {config.description || "未填写配置说明"}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="purchase-config-dialog__empty">当前还没有可选配置，请先去查询系统创建并保存配置。</div>
        )}

        <div className="surface-actions">
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
          <button
            className="accent-button"
            type="button"
            disabled={!selectedConfigId || !hasConfigs || isSubmitting}
            onClick={() => {
              onConfirm?.();
            }}
          >
            {isSubmitting ? "处理中..." : actionLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
