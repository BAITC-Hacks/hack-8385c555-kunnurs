import React from 'react';

function decisionLabel(decision, catalog) {
  const measure = catalog.measures.find((item) => item.id === decision.measure_id);
  const district = catalog.districts.find((item) => item.id === decision.district_id);
  return `${decision.measure_id} «${measure?.name || decision.measure_id}» (${district?.name || 'весь город'})`;
}

export function Alternatives({ alternatives, catalog, busy, onTry }) {
  if (!Array.isArray(alternatives)) return null;

  return <section className="alternatives" aria-labelledby="alternatives-title">
    <div className="alternatives-heading">
      <div><span className="section-kicker">ПРОВЕРЕНО СЕРВЕРОМ</span><h3 id="alternatives-title">Что можно улучшить</h3></div>
      <p>Каждый вариант заменяет одну меру в текущем наборе. Выбирайте варианты по одному: после выбора весь сценарий рассчитывается заново.</p>
    </div>
    {alternatives.length ? <div className="alternatives-grid">{alternatives.map((alternative) =>
      <article className="alternative-card" key={alternative.id}>
        <div className="alternative-card__gain"><span>Новый Score <b>{alternative.score.toFixed(2)}</b></span><strong>+{alternative.score_gain.toFixed(2)}</strong></div>
        <p className="alternative-card__change"><span>Заменить</span>{decisionLabel(alternative.removed, catalog)}</p>
        <p className="alternative-card__change"><span>На</span>{decisionLabel(alternative.added, catalog)}</p>
        <div className="alternative-card__facts"><span>Стоимость: <b>{alternative.total_cost}/100</b></span><span>Критических: <b>{alternative.critical_count}</b></span></div>
        {alternative.tradeoffs.length > 0 && <div className="alternative-card__tradeoffs"><strong>Компромиссы</strong><ul>{alternative.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}</ul></div>}
        <button type="button" className="button button--light" disabled={busy} onClick={() => onTry(alternative)}>Попробовать <span aria-hidden="true">→</span></button>
      </article>)}</div>
      : <p className="alternatives-empty">Среди замен одной меры сервер не нашёл варианта с более высоким Score. Это не означает, что другие наборы из пяти мер хуже.</p>}
  </section>;
}
