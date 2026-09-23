const signature = (decisions) => JSON.stringify(decisions.map(
  ({ measure_id, district_id }) => [measure_id, district_id || null],
).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))));

// Preserve the editor's slot order and reject advice for a different draft.
export function applyReplacement(decisions, alternative) {
  const same = (left, right) => left.measure_id === right.measure_id
    && (left.district_id || null) === (right.district_id || null);
  if (decisions.length !== 5 || decisions.filter((d) => same(d, alternative.removed)).length !== 1) {
    throw new Error('Этот совет устарел. Рассчитайте текущий набор заново.');
  }
  const next = decisions.map((decision) => {
    const source = same(decision, alternative.removed) ? alternative.added : decision;
    return { measure_id: source.measure_id, district_id: source.district_id || null };
  });
  if (signature(next) !== signature(alternative.scenario.decisions)) {
    throw new Error('Набор изменился после анализа. Рассчитайте его заново.');
  }
  return next;
}
