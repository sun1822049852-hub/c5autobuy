const DEFAULT_ITEMS = [
  {
    title: "最近登录任务",
    value: "等待接入真实任务流",
    meta: "下一阶段接登录抽屉与任务状态。",
  },
  {
    title: "最近错误",
    value: "当前无错误记录",
    meta: "后续会把请求失败与保存失败沉到这里。",
  },
  {
    title: "最近修改",
    value: "尚未发生配置改动",
    meta: "备注、API Key、代理修改会在这里留痕。",
  },
];


export function StatusStrip({
  backendStatus,
  recentError = "当前无错误记录",
  recentLoginTask = "等待接入真实任务流",
  recentModification = "尚未发生配置改动",
}) {
  const items = [
    {
      title: "最近登录任务",
      value: recentLoginTask,
      meta: `后端当前状态：${backendStatus}`,
    },
    {
      title: "最近错误",
      value: recentError,
      meta: "请求失败、保存失败和冲突提示会沉到这里。",
    },
    {
      title: "最近修改",
      value: recentModification,
      meta: "备注、API Key、代理和购买配置改动都会留痕。",
    },
  ];

  return (
    <section className="status-strip" aria-label="状态带">
      {items.map((item) => (
        <article key={item.title} className="status-strip__item">
          <div className="status-strip__title">{item.title}</div>
          <div className="status-strip__value">{item.value}</div>
          <div className="status-strip__meta">{item.meta}</div>
        </article>
      ))}
    </section>
  );
}
