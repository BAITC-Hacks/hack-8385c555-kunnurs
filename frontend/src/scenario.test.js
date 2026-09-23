import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DEMO_DECISIONS, previewScenario } from './scenario.js';

const catalog = JSON.parse(readFileSync(new URL('../../data/city.json', import.meta.url), 'utf8'));
const decision = (measure_id, district_id = null) => ({ measure_id, district_id });

test('PDF example fits the catalog rules', () => {
  const preview = previewScenario(DEMO_DECISIONS, catalog);
  assert.equal(preview.totalCost, 95);
  assert.equal(preview.remainingBudget, 5);
  assert.equal(preview.valid, true);
});

test('preview catches missing, repeated and over-budget decisions', () => {
  const missing = [...DEMO_DECISIONS.slice(0, 4), decision('')];
  assert.ok(previewScenario(missing, catalog).issues.some(({ code }) => code === 'decision_count'));

  const repeated = [decision('M7', 'nura'), decision('M7', 'esil'), decision('M10', 'nura'), decision('M12'), decision('M5', 'saryarka')];
  assert.ok(previewScenario(repeated, catalog).issues.some(({ code }) => code === 'duplicate_measure'));

  const expensive = [decision('M3', 'nura'), decision('M5', 'saryarka'), decision('M7', 'nura'), decision('M10', 'nura'), decision('M12')];
  assert.ok(previewScenario(expensive, catalog).issues.some(({ code }) => code === 'budget_exceeded'));
});

test('preview applies the two-per-direction rule and both conflict scopes', () => {
  const threeSocial = [decision('M7', 'nura'), decision('M8', 'nura'), decision('M9', 'nura'), decision('M10', 'nura'), decision('M12')];
  assert.ok(previewScenario(threeSocial, catalog).issues.some(({ code }) => code === 'direction_limit'));

  const anywhere = [decision('M1', 'nura'), decision('M3', 'esil'), decision('M10', 'nura'), decision('M12'), decision('M5', 'saryarka')];
  assert.ok(previewScenario(anywhere, catalog).issues.some(({ code }) => code === 'incompatible_measures'));

  const localConflict = [decision('M4', 'nura'), decision('M7', 'nura'), decision('M8', 'nura'), decision('M10', 'nura'), decision('M12')];
  assert.ok(previewScenario(localConflict, catalog).issues.some(({ code }) => code === 'incompatible_measures'));
  localConflict[0] = decision('M4', 'esil');
  assert.equal(previewScenario(localConflict, catalog).valid, true);
});

test('district measure needs a district and city measure rejects one', () => {
  const missingDistrict = DEMO_DECISIONS.map((item) => ({ ...item }));
  missingDistrict[0].district_id = null;
  assert.ok(previewScenario(missingDistrict, catalog).issues.some(({ code }) => code === 'invalid_district'));

  const cityWithDistrict = DEMO_DECISIONS.map((item) => ({ ...item }));
  cityWithDistrict[3].district_id = 'nura';
  assert.ok(previewScenario(cityWithDistrict, catalog).issues.some(({ code }) => code === 'city_has_district'));
});
