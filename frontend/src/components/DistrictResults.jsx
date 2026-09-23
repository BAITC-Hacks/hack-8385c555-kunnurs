import React from 'react';
import { METRICS } from '../scenario';

const number = (value) => Number(value).toFixed(2);
const signed = (value) => `${value > 0 ? '+' : ''}${number(value)}`;

export function DistrictResults({ catalog, baseline, result, selectedDistrict, onSelect, hasScenario }) {
  const district = result.districts.find(({ district_id }) => district_id === selectedDistrict) || result.districts[0];
  const initial = baseline.districts.find(({ district_id }) => district_id === district.district_id);
  const criticalCount = (districtId, source) => source.critical_indicators.filter(({ district_id }) => district_id === districtId).length;
  const districtName = (id) => catalog.districts.find(({ id: districtId }) => districtId === id)?.name || id;

  return <section id="districts" className="panel" aria-labelledby="districts-title">
    <div className="section-heading"><div><span className="section-kicker">02 / ПОКАЗАТЕЛИ</span><h2 id="districts-title">Что изменилось в районах</h2>
      <p>Один исходный набор для всех сценариев. Нажмите на район, чтобы увидеть все десять показателей.</p></div>
      <span className="legend"><i className="legend-dot" /> значение ниже {catalog.rules.critical_threshold} — критическое</span>
    </div>

    <div className="district-grid" role="group" aria-label="Выберите район">{result.districts.map((item) => {
      const critical = criticalCount(item.district_id, result);
      return <button type="button" key={item.district_id} className={district.district_id === item.district_id ? 'district-card district-card--selected' : 'district-card'} aria-pressed={district.district_id === item.district_id} onClick={() => onSelect(item.district_id)}>
        <span className="district-card__name">{item.name}</span><strong>{number(item.score)}</strong>
        <span className={item.score_delta > 0 ? 'delta delta--positive' : item.score_delta < 0 ? 'delta delta--negative' : 'delta'}>{hasScenario ? `${signed(item.score_delta)} к базе` : 'исходный балл'}</span>
        <span className="mini-track"><span style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }} /></span>
        <small>{critical ? `Критических: ${critical}` : 'Без критических значений'}</small>
      </button>;
    })}</div>

    <div className="score-formula" aria-label="Состав итогового Score">
      <div><span>Средний балл города · 70%</span><strong>{number(result.weighted_average)}</strong></div>
      <div><span>Слабейший район · 30%</span><strong>{number(result.weakest_district_score)}</strong></div>
      <div><span>Штраф за показатели ниже {catalog.rules.critical_threshold}</span><strong>−{result.critical_count}</strong></div>
      <p>Итог: 0,7 × средний балл + 0,3 × балл слабейшего района − число критических показателей.</p>
    </div>

    <div className="district-detail">
      <div className="detail-heading"><div><span className="section-kicker">РАЙОН КРУПНЫМ ПЛАНОМ</span><h3>{district.name}</h3></div>
        <p>Балл: <b>{number(initial.score)}</b> <span aria-hidden="true">→</span> <b>{number(district.score)}</b></p></div>
      <div className="indicator-profile" aria-hidden="true">
        <div className="indicator-profile__heading"><strong>Профиль показателей</strong><div><span className="profile-key profile-key--before" /> До <span className="profile-key profile-key--after" /> После</div></div>
        <div className="indicator-profile__scroll"><div className="indicator-profile__plot">
          <span className="indicator-profile__threshold" style={{ bottom: `${21 + 1.26 * catalog.rules.critical_threshold}px` }} />
          {METRICS.map(([code, label]) => <div className="indicator-profile__item" key={code} title={`${label}: ${number(initial.indicators[code])} → ${number(district.indicators[code])}`}>
            <span className="indicator-profile__bars"><i style={{ height: `${initial.indicators[code]}%` }} /><b className={district.indicators[code] < catalog.rules.critical_threshold ? 'is-critical' : ''} style={{ height: `${district.indicators[code]}%` }} /></span>
            <span>{code}</span>
          </div>)}
        </div></div>
        <small>Пунктир — порог критического значения {catalog.rules.critical_threshold}</small>
      </div>
      <div className="table-scroll"><table className="metrics-table"><caption>Показатели района {district.name}: исходные и после решений</caption>
        <thead><tr><th scope="col">Показатель</th><th scope="col">До</th><th scope="col">После</th><th scope="col">Изменение</th><th scope="col">Состояние</th></tr></thead>
        <tbody>{METRICS.map(([code, label]) => {
          const before = initial.indicators[code];
          const after = district.indicators[code];
          const delta = district.indicator_deltas[code];
          const critical = after < catalog.rules.critical_threshold;
          return <tr key={code} className={critical ? 'metric-row--critical' : ''}>
            <th scope="row"><span className="metric-code">{code}</span>{label}</th>
            <td>{number(before)}</td><td><strong>{number(after)}</strong></td>
            <td className={delta > 0 ? 'delta--positive' : delta < 0 ? 'delta--negative' : ''}>{signed(delta)}</td>
            <td>{critical ? <span className="critical-badge">Ниже {catalog.rules.critical_threshold}</span> : <span className="ok-label">От {catalog.rules.critical_threshold}</span>}</td>
          </tr>;
        })}</tbody>
      </table></div>
      <p className="table-note">100 означает лучшее состояние. Эффекты и синергии складываются до ограничения каждого показателя диапазоном 0–100.</p>
    </div>

    {hasScenario && <div className="impact-grid">
      <div><h3>Как сработали меры</h3><ul className="impact-list">{result.measure_effects.map((effect) => {
        const measure = catalog.measures.find(({ id }) => id === effect.measure_id);
        return <li key={effect.measure_id}><div><strong>{effect.measure_id} · {measure?.name}</strong><span>{effect.district_ids.length === catalog.districts.length ? 'Весь город' : effect.district_ids.map(districtName).join(', ')} · реализовано {Math.round(effect.realized_fraction * 100)}% за {catalog.rules.horizon_quarters} кв.</span></div><b>{effect.cost} ед.</b></li>;
      })}</ul></div>
      <div className="synergy-panel"><h3>Синергии</h3>{result.applied_synergies.length
        ? <ul>{result.applied_synergies.map((item) => <li key={item.measures.join('-')}><strong>{item.measures.join(' + ')}</strong><span>{districtName(item.district_id)} · {Object.entries(item.effects).map(([metric, value]) => `${metric} +${value}`).join(', ')}</span></li>)}</ul>
        : <p>В этом наборе синергии не сработали.</p>}
        <small>Показанные эффекты даны до ограничения 0–100. Они не складываются напрямую в Score.</small>
      </div>
    </div>}
  </section>;
}
