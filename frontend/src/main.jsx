import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { applyReplacement } from './scenario';
import './styles.css';

const directions = { transport: 'Транспорт', ecology: 'Озеленение и экология', social: 'Социальная инфраструктура', safety: 'Безопасность', services: 'Городской сервис' };
const aiModeLabels = { live: 'AI: live', mock: 'AI: шаблон (mock)', fallback: 'AI: шаблон (fallback)' };
const objectiveLabels = { best_score: 'Лучший Score', lowest_cost: 'Самая дешёвая из улучшающих', most_critical: 'Минимум критических показателей' };
const demo = [
  { measure_id: 'M7', district_id: 'nura' },
  { measure_id: 'M8', district_id: 'nura' },
  { measure_id: 'M10', district_id: 'nura' },
  { measure_id: 'M12', district_id: null },
  { measure_id: 'M5', district_id: 'saryarka' },
];

function App() {
  const [catalog, setCatalog] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [decisions, setDecisions] = useState(demo);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);

  useEffect(() => {
    let active = true;
    Promise.all([api('/api/health'), api('/api/catalog'), api('/api/baseline')])
      .then(([, data, initial]) => { if (active) { setCatalog(data); setBaseline(initial); } })
      .catch(() => { if (active) setError('Не удалось загрузить данные. Проверьте доступность сервера и обновите страницу.'); });
    return () => { active = false; };
  }, []);

  function update(index, next) {
    setDecisions((previous) => previous.map((decision, i) => i === index ? next : decision));
    setResponse(null);
    setError('');
  }

  async function calculate(nextDecisions = decisions) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    setResponse(null);
    try { setResponse(await api('/api/simulations/analyze', { decisions: nextDecisions })); }
    catch (cause) { setError(cause.message || 'Ошибка соединения. Попробуйте ещё раз.'); }
    finally { submitting.current = false; setBusy(false); }
  }

  function apply(alternative) {
    if (submitting.current) return;
    try {
      const next = applyReplacement(decisions, alternative);
      setDecisions(next);
      calculate(next);
    } catch (cause) { setError(cause.message); }
  }

  function describe(decision) {
    const measure = catalog.measures.find((m) => m.id === decision.measure_id);
    const district = catalog.districts.find((d) => d.id === decision.district_id);
    return `${measure.id} · ${measure.name} — ${district?.name || 'Весь город'}`;
  }

  const cost = catalog ? decisions.reduce((sum, decision) => sum + catalog.measures.find((measure) => measure.id === decision.measure_id).cost, 0) : 0;
  const result = response?.result || baseline;

  return <main>
    <header><p className="eyebrow">HackAlem AI · городской симулятор</p><h1>Аким на 5 часов</h1><p>Пять решений. Бюджет 100. Два условных года, чтобы улучшить жизнь города.</p></header>
    {error && <p role="alert" className="error">{error}</p>}
    {!catalog && !error && <p>Загружаем районы и мероприятия…</p>}
    {catalog && <>
      <section className="stats" aria-label="Сводка сценария">
        <article><span>Бюджет</span><strong className={cost > 100 ? 'danger' : ''}>{cost} / {catalog.rules.budget}</strong></article>
        <article><span>Astana Quality of Life Score</span><strong>{result.score.toFixed(2)}</strong></article>
        <article><span>Критические показатели</span><strong>{result.critical_count}</strong></article>
      </section>
      <section><h2>Ваши решения</h2><p>Ровно 5 разных мер, не более 2 на направление. Для городских мер район не выбирается.</p>
        <form onSubmit={(event) => { event.preventDefault(); calculate(); }}><fieldset disabled={busy}>
          {decisions.map((decision, index) => {
            const measure = catalog.measures.find((item) => item.id === decision.measure_id);
            return <div className="decision" key={index}>
              <label>Решение {index + 1}<select value={decision.measure_id} onChange={(event) => {
                const next = catalog.measures.find((item) => item.id === event.target.value);
                update(index, { measure_id: next.id, district_id: next.scope === 'city' ? null : decision.district_id || 'nura' });
              }}>{Object.entries(directions).map(([key, label]) => <optgroup label={label} key={key}>{catalog.measures.filter((item) => item.direction === key).map((item) => <option value={item.id} key={item.id}>{item.id} · {item.name} · {item.cost} ед.</option>)}</optgroup>)}</select></label>
              <label>Район<select value={decision.district_id || ''} disabled={measure.scope === 'city'} onChange={(event) => update(index, { ...decision, district_id: event.target.value })}>
                {measure.scope === 'city' ? <option value="">Весь город</option> : catalog.districts.map((district) => <option value={district.id} key={district.id}>{district.name}</option>)}
              </select></label>
              <small>Лаг: {measure.lag_quarters} кв.</small>
            </div>;
          })}
          {cost > catalog.rules.budget && <p className="danger">Превышение бюджета: {cost - catalog.rules.budget}. Измените набор мер.</p>}
          <button disabled={busy || cost > catalog.rules.budget}>{busy ? 'Считаем…' : 'Рассчитать сценарий'}</button>
        </fieldset></form>
      </section>
      {busy && <p role="status">Рассчитываем выбранный набор и проверяем новые рекомендации…</p>}
      <section><h2>{response ? 'Результат сценария' : 'Исходное состояние'}</h2>
        {response && <p>Изменение Score: {result.score_delta > 0 ? '+' : ''}{result.score_delta.toFixed(2)} · Остаток бюджета: {result.remaining_budget}</p>}
        <div className="table-scroll"><table><thead><tr><th>Район</th><th>Баллы</th><th>Изменение</th></tr></thead><tbody>{result.districts.map((district) => <tr key={district.district_id}><td>{district.name}</td><td>{district.score.toFixed(2)}</td><td>{district.score_delta > 0 ? '+' : ''}{district.score_delta.toFixed(2)}</td></tr>)}</tbody></table></div>
        <p className="muted">Score = 0.7 × средний балл + 0.3 × балл слабейшего района − число показателей ниже 40.</p>
      </section>
      {response && <section aria-live="polite"><h2>Объяснение результата</h2><div className="analysis-status"><span className="ai-badge">{aiModeLabels[response.analysis.mode]}</span><p className="notice">{response.analysis.notice}</p></div><p>{response.analysis.summary}</p>
        {[['Сильные стороны', 'strengths'], ['Риски и компромиссы', 'risks']].map(([label, key]) => <div key={key} data-analysis={key}><h3>{label}</h3><ul>{response.analysis[key].map((text, index) => <li key={index}>{text}</li>)}</ul></div>)}
        <div data-analysis="recommendations"><h3>Следующий шаг</h3>
          {response.alternatives?.length ? <>
            <p className="muted">Проверены все допустимые замены одного решения. Одна карточка может быть лучшей по нескольким критериям. «Применить» заменит одну меру в форме и пересчитает набор; прежние советы исчезнут.</p>
            <div className="alternatives">{response.alternatives.map((alternative) => <article className="alternative" data-alternative-id={alternative.id} key={alternative.id}>
              <div className="objective-labels">{(alternative.objectives || []).map((objective) => <span key={objective}>{objectiveLabels[objective]}</span>)}</div>
              <p><span className="muted">Заменить:</span> {describe(alternative.removed)}</p>
              <p><strong>На:</strong> {describe(alternative.added)}</p>
              <p>Score: {result.score.toFixed(2)} → <strong>{alternative.score.toFixed(2)}</strong> (+{alternative.score_gain.toFixed(2)})<br />Бюджет: {result.total_cost} → {alternative.total_cost}/100 · Остаток: {alternative.remaining_budget}<br />Критические: {result.critical_count} → {alternative.critical_count}</p>
              {alternative.tradeoffs.length ? <div><strong>Ухудшения относительно текущего набора:</strong><ul>{alternative.tradeoffs.map((text, i) => <li key={i}>{text}</li>)}</ul></div> : <p>Снижения отдельных показателей нет.</p>}
              <button type="button" disabled={busy} onClick={() => apply(alternative)} aria-label={`Применить: ${describe(alternative.added)}`}>Применить</button>
            </article>)}</div>
          </> : <ul>{response.analysis.recommendations.map((text, index) => <li key={index}>{text}</li>)}</ul>}
        </div>
      </section>}
    </>}
    <footer>Синтетические данные · Учебная модель, не прогноз развития Астаны</footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
