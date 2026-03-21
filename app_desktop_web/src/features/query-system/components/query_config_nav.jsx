export function QueryConfigNav({
  configs,
  isDeleteMode,
  isCreatingConfig,
  isLoading,
  onDeleteConfig,
  onOpenCreateConfigDialog,
  onSelectConfig,
  onToggleDeleteMode,
}) {
  return (
    <section className={`query-config-nav${isDeleteMode ? " is-delete-mode" : ""}`}>
      <div className="query-config-nav__header">
        <div>
          <div className="query-config-nav__eyebrow">Configs</div>
          <h2 className="query-config-nav__title">配置管理</h2>
        </div>
        <div className="query-config-nav__toolbar">
          <button
            className="query-config-nav__icon-button query-config-nav__icon-button--create"
            type="button"
            aria-label="新建配置"
            disabled={isCreatingConfig}
            onClick={onOpenCreateConfigDialog}
          >
            +
          </button>
          <button
            className={`query-config-nav__icon-button query-config-nav__icon-button--delete${isDeleteMode ? " is-active" : ""}`}
            type="button"
            aria-label="切换配置删除模式"
            onClick={onToggleDeleteMode}
          >
            -
          </button>
        </div>
      </div>
      <nav aria-label="配置管理导航" className="query-config-nav__list">
        {isLoading ? (
          <div className="query-config-nav__empty">正在加载配置...</div>
        ) : null}
        {!isLoading && configs.length === 0 ? (
          <div className="query-config-nav__empty">还没有配置，先用右上角 + 创建一份。</div>
        ) : null}
        {configs.map((config) => (
          <div key={config.config_id} className="query-config-nav__item-shell">
            <button
              className={`query-config-nav__item${config.isSelected ? " is-active" : ""}`}
              type="button"
              onClick={() => onSelectConfig(config.config_id)}
            >
              <span className="query-config-nav__item-title">{config.name}</span>
              <span className="query-config-nav__item-meta">{config.statusText}</span>
            </button>
            {isDeleteMode ? (
              <button
                className="query-config-nav__delete"
                type="button"
                aria-label={`删除配置 ${config.name}`}
                onClick={() => onDeleteConfig(config)}
              >
                -
              </button>
            ) : null}
          </div>
        ))}
      </nav>
    </section>
  );
}
