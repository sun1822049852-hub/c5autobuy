export function OverviewCards({ activeFilter, cards, className = "", onSelect }) {
  const gridClassName = ["overview-grid", className].filter(Boolean).join(" ");

  return (
    <section className={gridClassName} aria-label="概览卡片">
      {cards.map((card) => (
        <button
          key={card.id}
          aria-label={`${card.label} ${card.value}`}
          className={`overview-card${card.id === activeFilter ? " is-active" : ""}`}
          type="button"
          onClick={() => onSelect(card.id)}
        >
          <span className="overview-card__label">{card.label}</span>
          <span className="overview-card__value">{card.value}</span>
          <span className="overview-card__hint">{card.hint}</span>
        </button>
      ))}
    </section>
  );
}
