import { getLoginTaskEventDisplayMessage, getLoginTaskStateLabel } from "../login_task_state_labels.js";

function renderTaskEvents(task) {
  if (!task?.events?.length) {
    return (
      <div className="drawer-note">
        登录任务尚未开始，确认代理后点击下方按钮发起登录。
      </div>
    );
  }

  return (
    <div className="drawer-list">
      {task.events.map((event) => (
        <div key={`${event.state}-${event.timestamp}`} className="drawer-inventory">
          <div className="drawer-inventory__title">{getLoginTaskEventDisplayMessage(event)}</div>
          <div className="drawer-inventory__meta">{event.timestamp}</div>
        </div>
      ))}
    </div>
  );
}


export function LoginDrawer({
  account,
  isStarting,
  onClose,
  onStartLogin,
  open,
  task,
}) {
  if (!open || !account) {
    return null;
  }

  return (
    <aside aria-label="登录配置" className="drawer-surface" role="complementary">
      <div className="surface-header">
        <div>
          <h2 className="surface-title">登录配置</h2>
          <p className="surface-subtitle">登录会打开浏览器，请按页面提示完成扫码。</p>
        </div>
        <button className="ghost-button" type="button" onClick={onClose}>关闭</button>
      </div>

      <div className="drawer-stack">
        <div className="drawer-card">
          <div className="drawer-card__label">当前账号</div>
          <div className="drawer-card__value">{account.display_name}</div>
        </div>

        <div className="drawer-card">
          <div className="drawer-card__label">浏览器代理</div>
          <div className="drawer-card__value">{account.browser_proxy_display || "未获取IP"}</div>
        </div>

        <div className="drawer-card">
          <div className="drawer-card__label">API代理</div>
          <div className="drawer-card__value">{account.api_proxy_display || "未获取IP"}</div>
        </div>

        <div className="drawer-card">
          <div className="drawer-card__label">任务状态</div>
          <div className="drawer-card__value">{getLoginTaskStateLabel(task?.state)}</div>
        </div>

        {renderTaskEvents(task)}
      </div>

      <div className="surface-actions">
        <button
          className="accent-button"
          disabled={isStarting}
          type="button"
          onClick={onStartLogin}
        >
          发起登录
        </button>
      </div>
    </aside>
  );
}
