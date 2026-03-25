export function OverviewCards({ activeFilter, cards, className = "", onSelect, style }) {
  const gridClassName = ["overview-grid", className].filter(Boolean).join(" ");

  return (
    <section
      aria-label="概览卡片"
      className={gridClassName}
      style={{
        ...style,
        "--overview-columns": String(cards.length),
      }}
    >
      {cards.map((card) => (
        <button
          key={card.id}
          aria-label={`${card.label} ${card.value}`}
          className={`overview-card${(card.isActive ?? card.id === activeFilter) ? " is-active" : ""}`}
          type="button"
          onClick={() => {
            if (typeof card.onClick === "function") {
              card.onClick();
              return;
            }

            onSelect?.(card.id);
          }}
        >
          <span className="overview-card__label">{card.label}</span>
          <span className="overview-card__value">{card.value}</span>
          <span className="overview-card__hint">{card.hint}</span>
        </button>
      ))}
    </section>
  );
}
