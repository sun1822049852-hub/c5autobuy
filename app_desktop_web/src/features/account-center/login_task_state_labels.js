// C5 登录任务状态的用户显示映射唯一维护点。
const LOGIN_TASK_STATE_LABELS = Object.freeze({
  idle: "未开始",
  pending: "已创建",
  starting_browser: "正在启动浏览器",
  waiting_for_scan: "等待扫码",
  captured_login_info: "已获取登录信息",
  waiting_for_browser_close: "等待关闭登录窗口",
  saving_account: "正在保存登录状态",
  running: "进行中",
  succeeded: "登录完成",
  success: "登录完成",
  failed: "登录失败",
  cancelled: "已取消",
  conflict: "账号冲突，等待确认",
});

export function getLoginTaskStateLabel(state) {
  const normalized = String(state || "").trim();
  if (!normalized) {
    return LOGIN_TASK_STATE_LABELS.idle;
  }
  return LOGIN_TASK_STATE_LABELS[normalized] || "状态更新中";
}

export function getLoginTaskEventDisplayMessage(event) {
  const message = String(event?.message || "").trim();
  return message || getLoginTaskStateLabel(event?.state);
}
