import React from 'react';
import { Alternatives } from './Alternatives';

const modeLabels = {
  live: 'AI: live',
  mock: 'AI: шаблон (mock)',
  fallback: 'AI: шаблон (fallback)',
};

const sourceLabels = {
  provider: 'Ответ модели',
  cache: 'Проверенный ответ из кэша',
  template: 'Шаблонное объяснение',
};

export function AnalysisPanel({ result, analysis, alternatives, catalog, busy, onRetry, onTryAlternative }) {
  const mode = analysis?.mode;
  return <section id="analysis" className="panel analysis-panel" aria-labelledby="analysis-title" aria-live="polite">
    <div className="section-heading"><div><span className="section-kicker">03 / АНАЛИЗ</span><h2 id="analysis-title">Почему получился такой результат</h2>
      <p>AI объясняет рассчитанный сервером сценарий. Score и стоимость определяет только модель расчёта.</p></div></div>
    {busy ? <div className="analysis-pending"><span className="spinner" aria-hidden="true" /><div><strong>Считаем сценарий и готовим объяснение…</strong><p>Ответ AI может занять до 12 секунд; при ошибке сервер вернёт явно обозначенный шаблон.</p></div></div>
      : analysis ? <>
        <div className="analysis-status"><span className={`ai-badge ai-badge--${mode}`}>{modeLabels[mode] || 'AI: режим неизвестен'}</span>
          <span className="analysis-source">{sourceLabels[analysis.source] || sourceLabels.template}</span>
          <p className="notice">{analysis.notice}</p></div>
        <p className="analysis-summary">{analysis.summary}</p>
        <div className="analysis-grid">{[
          ['Сильные стороны', 'strengths', 'strengths'],
          ['Риски и компромиссы', 'risks', 'risks'],
          ['Что проверить дальше', 'recommendations', 'recommendations'],
        ].filter(([, key]) => key !== 'recommendations' || !alternatives?.length).map(([title, key, style]) => <div className={`analysis-card analysis-card--${style}`} data-analysis={key} key={key}><h3>{title}</h3><ul>{analysis[key].map((item, index) => <li key={index}>{item}</li>)}</ul></div>)}</div>
        <Alternatives result={result} alternatives={alternatives} catalog={catalog} busy={busy} onTry={onTryAlternative} />
        <div className="analysis-footer"><p>Текст AI помогает понять результат. Цифры альтернатив рассчитаны сервером.</p><button type="button" className="button button--light" onClick={onRetry}>Повторить анализ</button></div>
      </> : <div className="empty-state"><span aria-hidden="true">✦</span><h3>Анализ появится после расчёта</h3><p>Выберите пять мер и нажмите «Рассчитать и получить AI-анализ».</p></div>}
  </section>;
}
