export const DEMO_DECISIONS = [
  { measure_id: 'M7', district_id: 'nura' },
  { measure_id: 'M8', district_id: 'nura' },
  { measure_id: 'M10', district_id: 'nura' },
  { measure_id: 'M12', district_id: null },
  { measure_id: 'M5', district_id: 'saryarka' },
];

export const DIRECTIONS = {
  transport: 'Транспорт',
  ecology: 'Экология',
  social: 'Социальная сфера',
  safety: 'Безопасность',
  services: 'Городские сервисы',
};

export const METRICS = [
  ['T1', 'Разгрузка дорог'], ['T2', 'Общественный транспорт'],
  ['E1', 'Озеленение'], ['E2', 'Качество воздуха'],
  ['S1', 'Школы и детсады'], ['S2', 'Медицинская помощь'],
  ['B1', 'Безопасность улиц'], ['B2', 'Безопасность дорог'],
  ['C1', 'Надёжность ЖКХ'], ['C2', 'Обращения жителей'],
];

export function previewScenario(decisions, catalog) {
  const measures = new Map(catalog.measures.map((measure) => [measure.id, measure]));
  const districts = new Set(catalog.districts.map((district) => district.id));
  const issues = [];
  const add = (code, message, slots = []) => issues.push({ code, message, slots });
  const selected = decisions.map((decision, slot) => ({ ...decision, slot, measure: measures.get(decision.measure_id) }));
  const active = selected.filter(({ measure_id }) => measure_id);
  const totalCost = active.reduce((sum, { measure }) => sum + (measure?.cost || 0), 0);
  const directions = Object.fromEntries(Object.keys(DIRECTIONS).map((direction) => [direction, 0]));

  if (active.length !== catalog.rules.decision_count) {
    add('decision_count', `Выберите ровно ${catalog.rules.decision_count} мероприятий.`);
  }

  for (const entry of active) {
    if (!entry.measure) {
      add('unknown_measure', 'Выбрано неизвестное мероприятие.', [entry.slot]);
      continue;
    }
    directions[entry.measure.direction] += 1;
    if (entry.measure.scope === 'city' && entry.district_id != null) {
      add('city_has_district', `${entry.measure.id}: для городской меры район не выбирается.`, [entry.slot]);
    }
    if (entry.measure.scope === 'district' && !districts.has(entry.district_id)) {
      add('invalid_district', `${entry.measure.id}: выберите район.`, [entry.slot]);
    }
  }

  const byMeasure = new Map();
  for (const entry of active) {
    byMeasure.set(entry.measure_id, [...(byMeasure.get(entry.measure_id) || []), entry]);
  }
  for (const [measureId, entries] of byMeasure) {
    if (entries.length > 1) {
      add('duplicate_measure', `${measureId} выбран несколько раз. Каждая мера доступна только один раз.`, entries.map(({ slot }) => slot));
    }
  }

  if (totalCost > catalog.rules.budget) {
    add('budget_exceeded', `Бюджет превышен на ${totalCost - catalog.rules.budget} ед. Уберите или замените меру.`);
  }
  for (const [direction, count] of Object.entries(directions)) {
    if (count > catalog.rules.max_per_direction) {
      add('direction_limit', `${DIRECTIONS[direction]}: не более ${catalog.rules.max_per_direction} мер.`, active.filter(({ measure }) => measure?.direction === direction).map(({ slot }) => slot));
    }
  }

  for (const conflict of catalog.conflicts) {
    const [first, second] = conflict.measures.map((id) => active.find(({ measure_id }) => measure_id === id));
    if (first && second && (conflict.scope === 'anywhere' || first.district_id === second.district_id)) {
      add('incompatible_measures', conflict.reason, [first.slot, second.slot]);
    }
  }

  return {
    totalCost,
    remainingBudget: catalog.rules.budget - totalCost,
    directions,
    issues,
    valid: issues.length === 0,
  };
}
