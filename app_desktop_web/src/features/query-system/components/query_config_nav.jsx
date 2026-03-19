export function QueryConfigNav({
  configs,
  isCreatingConfig,
  isLoading,
  onDeleteConfig,
  onOpenCreateConfigDialog,
  onSelectConfig,
}) {
  return (
    <section className="query-config-nav">
      <div className="query-config-nav__header">
        <div>
          <div className="query-config-nav__eyebrow">Configs</div>
          <h2 className="query-config-nav__title">查询配置</h2>
        </div>
        <button
          className="ghost-button query-config-nav__create"
          type="button"
          disabled={isCreatingConfig}
          onClick={onOpenCreateConfigDialog}
        >
          {isCreatingConfig ? "创建中..." : "新建配置"}
        </button>
      </div>
      <nav aria-label="查询配置导航" className="query-config-nav__list">
        {isLoading ? (
          <div className="query-config-nav__empty">正在加载配置...</div>
        ) : null}
        {!isLoading && configs.length === 0 ? (
          <div className="query-config-nav__empty">还没有查询配置，先在这里创建第一份工作台。</div>
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
            <button
              className="ghost-button query-config-nav__delete"
              type="button"
              aria-label={`删除配置 ${config.name}`}
              onClick={() => onDeleteConfig(config)}
            >
              删除
            </button>
          </div>
        ))}
      </nav>
    </section>
  );
}
