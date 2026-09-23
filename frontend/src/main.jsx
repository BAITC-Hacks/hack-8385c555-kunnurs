import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { DEMO_DECISIONS, applyReplacement, previewScenario } from './scenario';
import { ScenarioEditor } from './components/ScenarioEditor';
import { DistrictResults } from './components/DistrictResults';
import { AnalysisPanel } from './components/AnalysisPanel';
import { ComparePanel } from './components/ComparePanel';
import './styles.css';
import { LanguageProvider, LanguageSwitcher, Localized } from './i18n';

const STORAGE_KEY = 'akim-saved-scenario-v1';
const score = (value) => Number(value).toFixed(2);

function readSavedScenario() {
  try {
    const item = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return item?.result?.dataset_version && typeof item.result.score === 'number' && Array.isArray(item.decisions) ? item : null;
  } catch {
    return null;
  }
}

function App() {
  const [catalog, setCatalog] = useState(null);
  const [baseline, setBaseline] = useState(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);
  const [decisions, setDecisions] = useState(DEMO_DECISIONS.map((item) => ({ ...item })));
  const [response, setResponse] = useState(null);
  const [requestError, setRequestError] = useState('');
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [selectedDistrict, setSelectedDistrict] = useState('nura');
  const [saved, setSaved] = useState(readSavedScenario);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError('');
    Promise.all([api('/api/health'), api('/api/catalog'), api('/api/baseline')])
      .then(([, data, initial]) => {
        if (!active) return;
        setCatalog(data);
        setBaseline(initial);
        setLoading(false);
      })
      .catch((error) => {
        if (!active) return;
        setLoadError(error.message);
        setLoading(false);
      });
    return () => { active = false; };
  }, [loadAttempt]);

  const preview = useMemo(() => catalog ? previewScenario(decisions, catalog) : null, [decisions, catalog]);
  const result = response?.result || baseline;

  function changeDecision(index, next) {
    setDecisions((previous) => previous.map((decision, slot) => slot === index ? next : decision));
    setResponse(null);
    setRequestError('');
  }

  function restoreDemo() {
    setDecisions(DEMO_DECISIONS.map((item) => ({ ...item })));
    setSelectedDistrict('nura');
    setResponse(null);
    setRequestError('');
  }

  function clearDecisions() {
    setDecisions(Array.from({ length: catalog.rules.decision_count }, () => ({ measure_id: '', district_id: null })));
    setResponse(null);
    setRequestError('');
  }

  async function requestAnalysis(nextDecisions) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setRequestError('');
    setResponse(null);
    const payload = { decisions: nextDecisions.map(({ measure_id, district_id }) =>
      district_id == null ? { measure_id } : { measure_id, district_id }) };
    try {
      const data = await api('/api/simulations/analyze', { body: payload });
      if (data.result?.dataset_version !== catalog.version) {
        throw new Error('Версия данных изменилась. Обновите страницу и рассчитайте набор снова.');
      }
      setResponse(data);
    } catch (error) {
      setRequestError(error.message || 'Не удалось рассчитать сценарий.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function calculate(event) {
    event?.preventDefault();
    if (!preview?.valid || busy || submitting.current) return;
    void requestAnalysis(decisions);
  }

  function tryAlternative(alternative) {
    if (!response || busy || submitting.current || !Array.isArray(alternative?.scenario?.decisions)) return;
    let nextDecisions;
    try { nextDecisions = applyReplacement(decisions, alternative); }
    catch (error) { setRequestError(error.message); return; }
    if (!previewScenario(nextDecisions, catalog).valid) {
      setRequestError('Сервер предложил недопустимый набор мер. Обновите страницу и попробуйте снова.');
      return;
    }
    setDecisions(nextDecisions);
    if (alternative.added?.district_id) setSelectedDistrict(alternative.added.district_id);
    void requestAnalysis(nextDecisions);
  }

  function saveComparison() {
    if (!response?.result) return;
    const item = { decisions: decisions.map((decision) => ({ ...decision })), result: response.result };
    setSaved(item);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(item)); } catch { /* In-memory comparison still works. */ }
  }

  function clearComparison() {
    setSaved(null);
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* Storage may be disabled. */ }
  }

  return <Localized><div className="site-shell">
    <header className="topbar"><a className="brand" href="#top" aria-label="Аким на 5 часов, наверх"><span className="brand-mark" aria-hidden="true">5</span><span>АКИМ <b>НА 5 ЧАСОВ</b></span></a>
      <nav aria-label="Разделы страницы"><a href="#scenario">Решения</a><a href="#districts">Районы</a><a href="#analysis">AI-анализ</a><a href="#compare">Сравнение</a></nav>
      <div className="topbar-tools"><span className={loadError ? 'connection connection--error' : 'connection'}><i aria-hidden="true" />{loadError ? 'API недоступен' : loading ? 'Подключаем API' : 'API подключён'}</span><LanguageSwitcher /></div>
    </header>

    <main id="top">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy"><span className="hero-eyebrow">ГОРОДСКОЙ СИМУЛЯТОР · HACKALEM AI</span>
          <h1 id="hero-title">Пять решений.<br /><em>Один город.</em></h1>
          <p>Распределите 100 условных единиц между городскими инициативами и увидьте, как изменится качество жизни пяти районов за два условных года.</p>
          <div className="hero-actions"><a className="button button--primary" href="#scenario">Собрать сценарий <span aria-hidden="true">→</span></a><span>Все данные синтетические. Это учебная модель, не прогноз для Астаны.</span></div>
        </div>
        <div className="score-panel" aria-live="polite"><span className="score-panel__eyebrow">ASTANA QUALITY OF LIFE SCORE</span>
          <span className="score-panel__label">{response ? 'Ваш рассчитанный сценарий' : 'Единое исходное состояние'}</span>
          <strong className="score-panel__value">{result ? score(result.score) : '—'}</strong>
          <span className="score-panel__delta">{response ? `${result.score_delta > 0 ? '+' : ''}${score(result.score_delta)} к исходному Score` : 'одинаково для всех участников'}</span>
          <div className="score-panel__meta"><div><span>Исходный Score</span><b>{baseline ? score(baseline.score) : '—'}</b></div>
            <div><span>Критических значений</span><b>{result?.critical_count ?? '—'}</b></div>
            <div><span>Остаток бюджета</span><b>{response ? `${result.remaining_budget} ед.` : '100 ед.'}</b></div></div>
        </div>
      </section>

      {loading && <section className="panel loading-panel" aria-live="polite"><span className="spinner" aria-hidden="true" /><div><h2>Загружаем город</h2><p>Получаем каталог, исходные показатели и состояние сервера.</p></div></section>}
      {loadError && <section className="panel error-panel" role="alert"><h2>Не удалось подключиться к backend</h2><p>{loadError}</p><p>Проверьте, что API запущен и адрес в <code>frontend/.env.local</code> верный.</p><button type="button" className="button button--primary" onClick={() => setLoadAttempt((count) => count + 1)}>Повторить подключение</button></section>}

      {catalog && baseline && !loadError && <>
        <div className="context-strip"><span>5 районов</span><span>10 показателей</span><span>14 мероприятий</span><span>8 кварталов</span><small>Версия данных: {catalog.version}</small></div>
        <ScenarioEditor catalog={catalog} decisions={decisions} preview={preview} busy={busy} onChange={changeDecision} onSubmit={calculate} onRestore={restoreDemo} onClear={clearDecisions} />
        {requestError && <div className="request-error" role="alert"><div><strong>Сценарий не рассчитан</strong><p>{requestError}</p></div><button type="button" className="button button--light" onClick={calculate}>Повторить</button></div>}
        <DistrictResults catalog={catalog} baseline={baseline} result={result} selectedDistrict={selectedDistrict} onSelect={setSelectedDistrict} hasScenario={Boolean(response)} />
        <AnalysisPanel result={response?.result} analysis={response?.analysis} alternatives={response?.alternatives} catalog={catalog} busy={busy} onRetry={calculate} onTryAlternative={tryAlternative} />
        <ComparePanel catalog={catalog} saved={saved} current={response?.result} onSave={saveComparison} onClear={clearComparison} />
      </>}
    </main>
    <footer className="footer"><div><strong>Аким на 5 часов</strong><p>Проверяйте решения на данных, а не на догадках.</p></div><p>Синтетический датасет · Score считает сервер · AI не меняет выбранные меры</p></footer>
  </div></Localized>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><LanguageProvider><App /></LanguageProvider></React.StrictMode>);
