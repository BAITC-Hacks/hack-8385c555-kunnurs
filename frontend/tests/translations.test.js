import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { messages, translate } from '../src/translations.js';
import { DIRECTIONS, METRICS, previewScenario } from '../src/scenario.js';

const catalog = JSON.parse(readFileSync(new URL('../../data/city.json', import.meta.url), 'utf8'));

test('all catalog names, directions, metrics and conflicts have complete translations', () => {
  assert.equal(new Set(messages.map(([key]) => key)).size, messages.length, 'duplicate translation keys');
  const keys = new Set(messages.map(([key]) => key));
  for (const label of [...catalog.measures.map((m) => m.name), ...catalog.districts.map((d) => d.name), ...catalog.conflicts.map((c) => c.reason), ...Object.values(DIRECTIONS), ...METRICS.map(([, label]) => label)]) assert(keys.has(label), label);
  for (const row of messages) {
    assert.equal(row.length, 3);
    for (const value of row) {
      assert(value.trim().length > 0);
      assert.deepEqual((value.match(/\{\d+\}/g) || []).sort(), (row[0].match(/\{\d+\}/g) || []).sort());
    }
  }
});

test('translated display values preserve IDs, numbers and the source dataset', () => {
  const original = JSON.stringify(catalog);
  assert.equal(translate('  Осталось: 5 ед. Остаток не повышает Score. ', 'en'), '  Remaining: 5 units. Unused budget does not increase Score. ');
  assert.equal(translate('M7 «Школа + детсад (модульное строительство)» (Нура)', 'en'), 'M7 “School + kindergarten (modular construction)” (Nura)');
  assert.equal(translate('M7 Нура · M12 город', 'kk'), 'M7 Нұра · M12 қала');
  assert.equal(translate('+3.99 к исходному Score', 'en'), '+3.99 vs. initial Score');
  assert.equal(translate('Транспорт: не более 2 мер.', 'en'), 'Transport: at most 2 measures.');
  for (const issue of previewScenario([], catalog).issues) assert.notEqual(translate(issue.message, 'en'), issue.message);
  assert.equal(translate('Score 56.54307', 'en'), 'Score 56.54307');
  assert.equal(translate('Новый неизвестный ответ', 'en'), 'Новый неизвестный ответ');
  assert.equal(translate('Решения', 'bad-locale'), 'Решения');
  assert.equal(JSON.stringify(catalog), original);
});
