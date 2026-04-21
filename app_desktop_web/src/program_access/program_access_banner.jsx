function resolveModeLabel(mode) {
  if (mode === "local_pass_through") {
    return "本地放行";
  }
  return mode || "未命名模式";
}


function resolveGuardLabel(guardEnabled) {
  return guardEnabled ? "关键动作守卫已启用" : "关键动作守卫尚未启用";
}


export function ProgramAccessBanner({ access, guardError = null }) {
  if (!access?.message && !guardError?.message) {
    return null;
  }

  return (
    <section className="program-access-banner" aria-label="程序访问状态" role="status">
      <div className="program-access-banner__eyebrow">PROGRAM ACCESS</div>
      {access?.message ? (
        <>
          <div className="program-access-banner__message">{access.message}</div>
          <div className="program-access-banner__meta">
            <span>{resolveModeLabel(access.mode)}</span>
            <span>{access.stage || "未标记阶段"}</span>
            <span>{resolveGuardLabel(access.guardEnabled)}</span>
          </div>
          <div className="program-access-banner__placeholder">{access.loginPlaceholderLabel}</div>
        </>
      ) : null}
      {guardError ? (
        <div className="program-access-banner__guard-error" role="alert">
          <span className="program-access-banner__guard-code">{guardError.code}</span>
          <span>{guardError.message}</span>
        </div>
      ) : null}
    </section>
  );
}
