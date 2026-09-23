import assert from 'node:assert/strict';
import test from 'node:test';
import { applyReplacement } from '../src/scenario.js';

const decisions = [
  { measure_id: 'M8', district_id: 'almaty' }, { measure_id: 'M9', district_id: 'esil' },
  { measure_id: 'M10', district_id: 'nura' }, { measure_id: 'M12', district_id: null },
  { measure_id: 'M5', district_id: 'saryarka' },
];
const added = { measure_id: 'M7', district_id: 'nura' };
const alternative = { removed: decisions[1], added, scenario: { decisions: [decisions[4], decisions[3], decisions[2], added, decisions[0]] } };

test('apply the single replacement, preserve slots and do not mutate server data', () => {
  const before = JSON.stringify({ decisions, alternative });
  const next = applyReplacement(decisions, alternative);
  assert.deepEqual(next, [decisions[0], added, ...decisions.slice(2)]);
  assert.equal(JSON.stringify({ decisions, alternative }), before);
  next[1].district_id = 'esil';
  assert.equal(added.district_id, 'nura');
});

test('reject stale advice after another slot changes', () => {
  const changed = decisions.map((d, i) => i === 0 ? { ...d, district_id: 'nura' } : d);
  assert.throws(() => applyReplacement(changed, alternative), /Набор изменился/);
});

test('reject a second application of the old replacement', () => {
  assert.throws(() => applyReplacement(applyReplacement(decisions, alternative), alternative), /устарел/);
});

test('allow relocation of the same measure and city measures with omitted district', () => {
  const city = decisions.map((d) => d.measure_id === 'M12' ? { measure_id: 'M12' } : d);
  const moved = { ...decisions[0], district_id: 'nura' };
  const next = applyReplacement(city, { removed: city[0], added: moved, scenario: { decisions: [moved, ...city.slice(1)] } });
  assert.equal(next[0].district_id, 'nura');
  assert.equal(next[3].district_id, null);
});
