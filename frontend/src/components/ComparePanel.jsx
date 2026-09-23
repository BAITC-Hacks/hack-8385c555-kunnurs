import React from 'react';

const score = (value) => Number(value).toFixed(2);

export function ComparePanel({ catalog, saved, current, onSave, onClear }) {
  const sameVersion = !saved || saved.result?.dataset_version === catalog.version;
  const measures = new Map(catalog.measures.map((measure) => [measure.id, measure]));
  const districts = new Map(catalog.districts.map((district) => [district.id, district.name]));
  const describe = (decisions) => decisions.map(({ measure_id, district_id }) =>
    `${measure_id} ${measures.get(measure_id)?.scope === 'city' ? 'город' : districts.get(district_id) || district_id}`
  ).join(' · ');

  return <section id="compare" className="panel compare-panel" aria-labelledby="compare-title">
    <div className="section-heading"><div><span className="section-kicker">04 / СРАВНЕНИЕ</span><h2 id="compare-title">Проверьте другой набор</h2>
      <p>Сохраните результат в этом браузере, измените меры и рассчитайте снова. Оба результата считаются из одной исходной базы.</p></div>
      {current && <button type="button" className="button button--light" onClick={onSave}>{saved ? 'Заменить сохранённый' : 'Сохранить для сравнения'}</button>}
    </div>

    {saved && !sameVersion ? <div className="inline-warning"><p>Сохранённый набор использует другую версию данных. Для честного сравнения сохраните новый результат.</p><button type="button" className="button button--text" onClick={onClear}>Удалить старый набор</button></div>
      : saved ? <>
        <div className="saved-scenario"><div><span className="summary-caption">СОХРАНЁННЫЙ СЦЕНАРИЙ</span><p>{describe(saved.decisions)}</p></div><button type="button" className="button button--text" onClick={onClear}>Убрать</button></div>
        {current ? <><div className="compare-highlight"><span>Разница с сохранённым набором</span><strong className={current.score >= saved.result.score ? 'delta--positive' : 'delta--negative'}>{current.score > saved.result.score ? '+' : ''}{score(current.score - saved.result.score)}</strong><span>пункта Score</span></div>
          <div className="table-scroll"><table className="compare-table"><caption>Сравнение двух рассчитанных сценариев</caption><thead><tr><th scope="col">Показатель</th><th scope="col">Сохранённый</th><th scope="col">Текущий</th></tr></thead>
            <tbody><tr><th scope="row">Astana Quality of Life Score</th><td>{score(saved.result.score)}</td><td>{score(current.score)}</td></tr>
              <tr><th scope="row">Стоимость</th><td>{saved.result.total_cost} ед.</td><td>{current.total_cost} ед.</td></tr>
              <tr><th scope="row">Слабейший район</th><td>{score(saved.result.weakest_district_score)}</td><td>{score(current.weakest_district_score)}</td></tr>
              <tr><th scope="row">Критические показатели</th><td>{saved.result.critical_count}</td><td>{current.critical_count}</td></tr></tbody></table></div>
          <p className="table-note">Наборы имеют версию данных {catalog.version}. Сравнение использует только ответы сервера.</p>
        </> : <p className="compare-prompt">Сценарий сохранён. Измените одну из мер или район и рассчитайте новый набор.</p>}
      </> : <div className="empty-state empty-state--compact"><span aria-hidden="true">↗</span><h3>Первый результат ещё не сохранён</h3><p>После расчёта сохраните его здесь. Например, перенесите M7 из Нуры в Есиль и сравните Score.</p></div>}
  </section>;
}
