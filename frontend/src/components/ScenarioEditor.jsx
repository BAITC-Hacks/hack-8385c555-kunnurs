import React from 'react';
import { DIRECTIONS } from '../scenario';
import { Localized } from '../i18n';

function effectText(effects) {
  return Object.entries(effects).map(([metric, value]) => `${metric} ${value > 0 ? '+' : ''}${value}`).join(' · ');
}

export function ScenarioEditor({ catalog, decisions, preview, busy, onChange, onSubmit, onRestore, onClear }) {
  const { rules } = catalog;
  const selectedCount = decisions.filter(({ measure_id }) => measure_id).length;
  const budgetPercent = Math.min(100, (preview.totalCost / rules.budget) * 100);

  return <Localized><section id="scenario" className="panel scenario-panel" aria-labelledby="scenario-title">
    <div className="section-heading">
      <div><span className="section-kicker">01 / РЕШЕНИЯ</span><h2 id="scenario-title">Соберите свой сценарий</h2>
        <p>Пять разных мер, минимум три направления, бюджет до {rules.budget} единиц. Районные меры действуют в одном районе, городские — во всех пяти.</p></div>
      <div className="heading-actions">
        <button type="button" className="button button--light" onClick={onRestore} disabled={busy}>Пример из задания</button>
        <button type="button" className="button button--text" onClick={onClear} disabled={busy}>Очистить</button>
      </div>
    </div>

    <div className="scenario-summary">
      <div className="budget-box">
        <div className="summary-line"><span>Предварительная стоимость</span><strong className={preview.remainingBudget < 0 ? 'text-danger' : ''}>{preview.totalCost} / {rules.budget}</strong></div>
        <div className="budget-track" role="meter" aria-label="Использовано бюджета" aria-valuemin="0" aria-valuemax={rules.budget} aria-valuenow={Math.min(preview.totalCost, rules.budget)}>
          <span className={preview.remainingBudget < 0 ? 'budget-fill budget-fill--over' : 'budget-fill'} style={{ width: `${budgetPercent}%` }} />
        </div>
        <small>{preview.remainingBudget < 0 ? `Перерасход: ${-preview.remainingBudget} ед.` : `Осталось: ${preview.remainingBudget} ед. Остаток не повышает Score.`}</small>
      </div>
      <div className="coverage-box"><span className="summary-caption">Направления · не более {rules.max_per_direction} мер на каждое</span>
        <div className="direction-list">{Object.entries(DIRECTIONS).map(([id, name]) =>
          <span className={preview.directions[id] > rules.max_per_direction ? 'direction-chip direction-chip--error' : preview.directions[id] ? 'direction-chip direction-chip--active' : 'direction-chip'} key={id}>{name} <b>{preview.directions[id]}</b></span>
        )}</div>
      </div>
    </div>

    <form onSubmit={onSubmit} noValidate>
      <fieldset disabled={busy} className="decision-fieldset">
        <legend className="sr-only">Выбор пяти управленческих решений</legend>
        <div className="decision-list">{decisions.map((decision, index) => {
          const measure = catalog.measures.find(({ id }) => id === decision.measure_id);
          const invalid = preview.issues.some(({ slots }) => slots.includes(index));
          return <div className={invalid ? 'decision-card decision-card--error' : 'decision-card'} key={index}>
            <span className="decision-number">{String(index + 1).padStart(2, '0')}</span>
            <div className="decision-fields">
              <label htmlFor={`measure-${index}`}>Мероприятие</label>
              <select id={`measure-${index}`} value={decision.measure_id} aria-invalid={invalid} onChange={(event) => {
                const nextMeasure = catalog.measures.find(({ id }) => id === event.target.value);
                onChange(index, { measure_id: event.target.value, district_id: nextMeasure?.scope === 'district' ? decision.district_id || catalog.districts[0].id : null });
              }}>
                <option value="">Выберите меру</option>
                {Object.entries(DIRECTIONS).map(([direction, name]) =>
                  <optgroup label={name} key={direction}>{catalog.measures.filter((item) => item.direction === direction).map((item) =>
                    <option value={item.id} key={item.id}>{item.id} · {item.name}</option>
                  )}</optgroup>
                )}
              </select>
              {measure && <span className="decision-effect">{effectText(measure.effects)} <span>до учёта лага</span></span>}
            </div>
            <div className="decision-district">
              <label htmlFor={`district-${index}`}>Район</label>
              <select id={`district-${index}`} value={measure?.scope === 'district' ? decision.district_id || '' : ''} disabled={!measure || measure.scope === 'city'} onChange={(event) => onChange(index, { ...decision, district_id: event.target.value })}>
                {measure?.scope === 'district'
                  ? catalog.districts.map((district) => <option value={district.id} key={district.id}>{district.name}</option>)
                  : <option value="">Весь город</option>}
              </select>
            </div>
            <div className="decision-meta">{measure
              ? <><strong>{measure.cost} ед.</strong><span>{measure.scope === 'city' ? 'Городская мера' : 'Районная мера'} · лаг {measure.lag_quarters} кв.</span></>
              : <span>Мера не выбрана</span>}</div>
          </div>;
        })}</div>

        <div className={preview.issues.length ? 'validation-area' : 'validation-area validation-area--success'} aria-live="polite">
          {preview.issues.length
            ? <><strong>Проверьте набор решений</strong><ul>{preview.issues.map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.message}</li>)}</ul></>
            : <p className="validation-success">✓ Набор допустим: {selectedCount} решений, бюджет соблюдён. Итог проверит сервер.</p>}
        </div>
        <div className="form-actions"><button className="button button--primary" type="submit" disabled={!preview.valid || busy}>{busy ? 'Рассчитываем…' : 'Рассчитать и получить AI-анализ'} <span aria-hidden="true">→</span></button>
          <span>Все вычисления Score выполняет backend.</span></div>
      </fieldset>
    </form>
  </section></Localized>;
}
