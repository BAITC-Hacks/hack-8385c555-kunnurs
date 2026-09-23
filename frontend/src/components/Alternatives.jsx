import React from 'react';
import { Localized } from '../i18n';

function decisionLabel(decision, catalog) {
  const measure = catalog.measures.find((item) => item.id === decision.measure_id);
  const district = catalog.districts.find((item) => item.id === decision.district_id);
  return `${decision.measure_id} «${measure?.name || decision.measure_id}» (${district?.name || 'весь город'})`;
}

const objectives = { best_score: 'Лучший Score', lowest_cost: 'Самая дешёвая из улучшающих', most_critical: 'Минимум критических показателей' };

export function Alternatives({ result, alternatives, catalog, busy, onTry }) {
  if (!Array.isArray(alternatives)) return null;

  return <Localized><section className="alternatives" aria-labelledby="alternatives-title">
    <div className="alternatives-heading">
      <div><span className="section-kicker">ВОЗМОЖНОСТИ ДЛЯ РОСТА</span><h3 id="alternatives-title">Следующий шаг</h3></div>
      <p>Сравните пользу, стоимость и компромиссы. «Применить» заменит одну меру и рассчитает новый результат.</p>
    </div>
    {alternatives.length ? <div className="alternatives-grid">{alternatives.map((alternative) =>
      <article className="alternative-card" data-alternative-id={alternative.id} key={alternative.id}>
        <div className="objective-labels">{(alternative.objectives || []).map((objective) => <span key={objective}>{objectives[objective]}</span>)}</div>
        <div className="alternative-card__gain"><span>Score {result?.score.toFixed(2)} → <b>{alternative.score.toFixed(2)}</b></span><strong>+{alternative.score_gain.toFixed(2)}</strong></div>
        <p className="alternative-card__change"><span>Заменить</span>{decisionLabel(alternative.removed, catalog)}</p>
        <p className="alternative-card__change"><span>На</span>{decisionLabel(alternative.added, catalog)}</p>
        <div className="alternative-card__facts"><span>Стоимость: {result?.total_cost} → <b>{alternative.total_cost}/100</b></span><span>Остаток: <b>{alternative.remaining_budget}</b></span><span>Критических: {result?.critical_count} → <b>{alternative.critical_count}</b></span></div>
        {alternative.tradeoffs.length > 0 ? <div className="alternative-card__tradeoffs"><strong>Ухудшения относительно текущего набора</strong><ul data-original-text lang="ru">{alternative.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}</ul></div> : <p className="table-note">Снижения отдельных показателей нет.</p>}
        <button type="button" className="button button--light" disabled={busy} onClick={() => onTry(alternative)} aria-label={`Применить: ${decisionLabel(alternative.added, catalog)}`}>Применить <span aria-hidden="true">→</span></button>
      </article>)}</div>
      : <p className="alternatives-empty">Замена одной меры не повышает Score. Попробуйте другую комбинацию решений.</p>}
  </section></Localized>;
}
