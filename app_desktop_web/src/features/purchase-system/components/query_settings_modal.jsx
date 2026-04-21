const MODE_COPY = {
  new_api: {
    hint: "单次 API 查询器，最小基础冷却必须 >= 1 秒。",
    label: "new API",
  },
  fast_api: {
    hint: "高速 API 查询器，最小基础冷却必须 >= 0.2 秒。",
    label: "fast API",
  },
  token: {
    hint: "浏览器 token 查询器建议 >= 10 秒，低于该值会在保存前二次提醒。",
    label: "浏览器 token",
  },
};

function getModeCopy(modeType) {
  return MODE_COPY[modeType] || {
    hint: "未命名查询器。",
    label: modeType || "未知查询器",
  };
}

export function QuerySettingsModal({
  draft,
  error,
  isLoading,
  isOpen,
  isReadonly = false,
  isSaving,
  onChange,
  onClose,
  onSave,
  warnings = [],
}) {
  if (!isOpen) {
    return null;
  }

  const modeRows = Array.isArray(draft?.modes) ? draft.modes : [];

  return (
    <div
      className="surface-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget && !isSaving) {
          onClose?.();
        }
      }}
    >
      <section aria-label="查询设置" className="dialog-surface query-settings-modal" role="dialog">
        <div className="surface-header">
          <div>
            <h2 className="surface-title">查询设置</h2>
            <p className="surface-subtitle">全局持久化保存，三个查询器独立控制基础冷却、商品最小冷却、随机冷却和每日运行时间窗。</p>
          </div>
          <button className="ghost-button" disabled={isSaving} type="button" onClick={onClose}>关闭</button>
        </div>

        {error ? <div className="query-settings-modal__feedback is-danger">{error}</div> : null}
        {!error && warnings.length ? (
          <div className="query-settings-modal__feedback is-warn">{warnings.join("；")}</div>
        ) : null}

        {isLoading ? (
          <div className="query-settings-modal__loading">正在读取当前查询设置...</div>
        ) : (
          <div className="query-settings-modal__list">
            {modeRows.map((mode) => {
              const modeCopy = getModeCopy(mode.mode_type);
              return (
                <article key={mode.mode_type} className="query-settings-modal__card">
                  <div className="query-settings-modal__card-header">
                    <div>
                      <div className="query-settings-modal__card-title">{modeCopy.label}</div>
                      <div className="query-settings-modal__card-hint">{modeCopy.hint}</div>
                    </div>
                    <label className="drawer-checkbox">
                      <input
                        checked={Boolean(mode.enabled)}
                        disabled={isReadonly}
                        type="checkbox"
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "enabled", event.target.checked);
                        }}
                      />
                      <span>启用该查询器</span>
                    </label>
                  </div>

                  <div className="query-settings-modal__field-grid">
                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 基础冷却最小`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly}
                        inputMode="decimal"
                        min={mode.mode_type === "new_api" ? "1" : (mode.mode_type === "fast_api" ? "0.2" : "0")}
                        step="0.01"
                        type="number"
                        value={mode.base_cooldown_min}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "base_cooldown_min", event.target.value);
                        }}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 基础冷却最大`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly}
                        inputMode="decimal"
                        min={mode.mode_type === "new_api" ? "1" : (mode.mode_type === "fast_api" ? "0.2" : "0")}
                        step="0.01"
                        type="number"
                        value={mode.base_cooldown_max}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "base_cooldown_max", event.target.value);
                        }}
                      />
                    </label>
                  </div>

                  <div className="query-settings-modal__field-grid">
                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 商品最小冷却`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly}
                        inputMode="decimal"
                        min="0"
                        step="0.01"
                        type="number"
                        value={mode.item_min_cooldown_seconds}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "item_min_cooldown_seconds", event.target.value);
                        }}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 商品冷却策略`}</span>
                      <select
                        className="form-select"
                        disabled={isReadonly}
                        value={mode.item_min_cooldown_strategy}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "item_min_cooldown_strategy", event.target.value);
                        }}
                      >
                        <option value="fixed">固定值</option>
                        <option value="divide_by_assigned_count">按实际分配数平摊</option>
                      </select>
                    </label>
                  </div>
                  <div className="query-settings-modal__card-hint">
                    固定值会直接作为该商品在当前查询器内的最小冷却；按实际分配数平摊会使用该值除以当前实际分配到该商品的查询器数量。
                  </div>

                  <div className="query-settings-modal__toggle-row">
                    <label className="drawer-checkbox">
                      <input
                        checked={Boolean(mode.random_delay_enabled)}
                        disabled={isReadonly}
                        type="checkbox"
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "random_delay_enabled", event.target.checked);
                        }}
                      />
                      <span>启用随机冷却</span>
                    </label>
                  </div>

                  <div className="query-settings-modal__field-grid">
                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 随机冷却最小`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly || !mode.random_delay_enabled}
                        inputMode="decimal"
                        min="0"
                        step="0.01"
                        type="number"
                        value={mode.random_delay_min}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "random_delay_min", event.target.value);
                        }}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 随机冷却最大`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly || !mode.random_delay_enabled}
                        inputMode="decimal"
                        min="0"
                        step="0.01"
                        type="number"
                        value={mode.random_delay_max}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "random_delay_max", event.target.value);
                        }}
                      />
                    </label>
                  </div>

                  <div className="query-settings-modal__toggle-row">
                    <label className="drawer-checkbox">
                      <input
                        checked={Boolean(mode.window_enabled)}
                        disabled={isReadonly}
                        type="checkbox"
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "window_enabled", event.target.checked);
                        }}
                      />
                      <span>启用每日时间窗</span>
                    </label>
                  </div>

                  <div className="query-settings-modal__field-grid">
                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 开始时间`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly || !mode.window_enabled}
                        step="60"
                        type="time"
                        value={mode.start_time}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "start_time", event.target.value);
                        }}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-label">{`${modeCopy.label} 结束时间`}</span>
                      <input
                        className="form-input"
                        disabled={isReadonly || !mode.window_enabled}
                        step="60"
                        type="time"
                        value={mode.end_time}
                        onChange={(event) => {
                          onChange?.(mode.mode_type, "end_time", event.target.value);
                        }}
                      />
                    </label>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        <div className="surface-actions">
          <button className="ghost-button" disabled={isSaving} type="button" onClick={onClose}>取消</button>
          <button
            className="accent-button"
            disabled={isLoading || isReadonly || isSaving || !draft}
            type="button"
            onClick={() => {
              onSave?.();
            }}
          >
            {isSaving ? "保存中..." : "保存"}
          </button>
        </div>
      </section>
    </div>
  );
}
