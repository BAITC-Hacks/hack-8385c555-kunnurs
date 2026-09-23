// Finite Chromium integration test. Serves the built files through CDP Fetch
// interception and calls FastAPI TestClient in mock mode: no server or paid AI.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(root, 'dist');
const project = dirname(root);
const python = process.env.TEST_PYTHON || join(project, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const executable = process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const temporaryRoot = realpathSync(tmpdir());
const profile = mkdtempSync(join(temporaryRoot, 'akim-recommendations-'));
const browser = spawn(executable, [
  '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking', 'about:blank',
], { windowsHide: true, stdio: 'ignore' });
let launchError, socket, lastAnalysis;
browser.on('error', (error) => { launchError = error; });
const deadline = Date.now() + 55000;
const pending = new Map();
const failures = [];
const submissions = [];
let sequence = 0;
let failNext = false;

async function until(check, description) {
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    if (failures.length) throw new Error(failures.join('; '));
    if (await check()) return;
    await delay(60);
  }
  throw new Error(`Timeout: ${description}`);
}

function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 12000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!result.exceptionDetails, `Browser evaluation failed: ${expression}`);
  return result.result.value;
}

async function intercept({ requestId, request }) {
  const path = new URL(request.url).pathname;
  let body = '', type = 'application/json', status = 200;
  if (request.method === 'OPTIONS') status = 204;
  else if (path.startsWith('/api/')) {
    const payload = request.postData ? JSON.parse(request.postData) : null;
    if (payload) submissions.push(payload);
    if (failNext && payload) {
      failNext = false;
      status = 503;
      body = JSON.stringify({ error: { issues: [{ message: 'Тестовый сбой соединения' }] } });
    } else {
      const result = spawnSync(python, ['-c', `
import json, sys
from fastapi.testclient import TestClient
from backend.app.main import app
request = json.loads(sys.argv[1])
with TestClient(app) as client:
    response = client.request(request['method'], request['path'], json=request['payload'])
    print(json.dumps({'status': response.status_code, 'body': response.json()}, ensure_ascii=True))
`, JSON.stringify({ method: request.method, path, payload })], {
        cwd: project, encoding: 'utf8', windowsHide: true, timeout: 10000,
        env: { ...process.env, AI_MODE: 'mock', OPENAI_API_KEY: '', PYTHONIOENCODING: 'utf-8' },
      });
      assert.equal(result.status, 0, 'Offline API process failed');
      const response = JSON.parse(result.stdout);
      status = response.status;
      body = JSON.stringify(response.body);
      if (path.endsWith('/analyze') && status === 200) lastAnalysis = response.body;
    }
  } else if (path === '/') {
    type = 'text/html'; body = readFileSync(join(dist, 'index.html'));
  } else if (/^\/assets\/[a-zA-Z0-9._-]+\.(js|css)$/.test(path)) {
    type = path.endsWith('.js') ? 'application/javascript' : 'text/css';
    body = readFileSync(join(dist, path.slice(1)));
  } else { status = 404; }
  await command('Fetch.fulfillRequest', { requestId, responseCode: status, body: Buffer.from(body).toString('base64'), responseHeaders: [
    { name: 'Content-Type', value: type }, { name: 'Access-Control-Allow-Origin', value: '*' },
    { name: 'Access-Control-Allow-Methods', value: 'GET, POST, OPTIONS' },
    { name: 'Access-Control-Allow-Headers', value: 'Content-Type' },
  ] });
}

async function select(slot, field, value) {
  await evaluate(`(() => {
    const element = document.querySelectorAll('.decision-card')[${slot}].querySelectorAll('select')[${field}];
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(element, ${JSON.stringify(value)});
    element.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
}
async function calculated() {
  await until(() => evaluate("!!document.querySelector('.notice') && !document.querySelector('form button').disabled"), 'analysis rendered');
}
async function userScenario() {
  await command('Page.navigate', { url: 'http://akim.test/' });
  await until(() => evaluate("document.querySelectorAll('.decision-card').length === 5"), 'page loaded');
  await select(0, 0, 'M8'); await select(0, 1, 'almaty');
  await select(1, 0, 'M9'); await select(1, 1, 'esil');
  await evaluate("document.querySelector('form button').click()");
  await calculated();
}
const normalize = (decisions) => decisions.map((d) => `${d.measure_id}:${d.district_id || ''}`).sort();

try {
  let port;
  await until(() => {
    try { port = Number(readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0]); return !!port; }
    catch { return false; }
  }, 'browser startup');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(5000) })).json();
  socket = new WebSocket(pages.find((p) => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser connection timeout')), 5000);
    socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
  });
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const waiting = pending.get(message.id);
      clearTimeout(waiting.timer); pending.delete(message.id);
      if (message.error) waiting.reject(new Error(message.error.message)); else waiting.resolve(message.result);
    }
    if (message.method === 'Fetch.requestPaused') intercept(message.params).catch((error) => failures.push(error.message));
    if (message.method === 'Runtime.exceptionThrown') failures.push('Uncaught browser exception');
  });
  await command('Page.enable'); await command('Runtime.enable');
  await command('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await userScenario();
  const risks = await evaluate("document.querySelector('[data-analysis=risks]').innerText");
  assert(risks.includes('S1') && risks.includes('S2') && risks.includes('19 из 100'));
  assert(await evaluate("document.querySelector('.impact-list').innerText.includes('62.5%')"), 'realized fraction must not round to 63%');
  const originalScore = lastAnalysis.result.score;
  await evaluate("document.querySelector('#compare .section-heading button').click()");
  assert.equal(await evaluate("JSON.parse(localStorage.getItem('akim-saved-scenario-v1')).result.score"), originalScore);
  const choices = structuredClone(lastAnalysis.alternatives);
  assert(choices.length >= 1);
  for (let i = 0; i < choices.length; i++) {
    if (i) await userScenario();
    const chosen = choices[i];
    const count = submissions.length;
    await evaluate(`(() => { const button = document.querySelectorAll('.alternative-card button')[${i}]; button.click(); button.click(); })()`);
    await calculated();
    assert.equal(submissions.length, count + 1, 'double click must not send duplicate requests');
    assert.deepEqual(normalize(submissions.at(-1).decisions), normalize(chosen.scenario.decisions));
    assert.equal(lastAnalysis.result.score, chosen.score);
    assert.equal(await evaluate("document.querySelector('.compare-highlight strong').textContent"), `+${(chosen.score - originalScore).toFixed(2)}`);
    assert.equal(await evaluate("document.querySelector('.score-panel__value').textContent"), chosen.score.toFixed(2));
    const form = await evaluate("Array.from(document.querySelectorAll('.decision-card'), row => { const fields = row.querySelectorAll('select'); return {measure_id: fields[0].value, district_id: fields[1].value || null}; })");
    assert.deepEqual(normalize(form), normalize(chosen.scenario.decisions));
    const cards = await evaluate("Array.from(document.querySelectorAll('.alternative-card'), card => card.dataset.alternativeId)");
    assert.deepEqual(cards, lastAnalysis.alternatives.map((a) => a.id));
  }
  failNext = true;
  await evaluate("document.querySelector('.alternative-card button').click()");
  await until(() => evaluate("document.querySelector('[role=alert]')?.innerText.includes('Тестовый сбой') && !document.querySelector('form button').disabled"), 'recoverable failure');
  assert.equal(await evaluate("document.querySelectorAll('.alternative-card').length"), 0);
  const failedDraft = structuredClone(submissions.at(-1));
  await evaluate("document.querySelector('form button').click()"); await calculated();
  assert.deepEqual(submissions.at(-1), failedDraft, 'retry must calculate the applied draft');
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert(await evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), 'mobile horizontal overflow');
  await select(0, 1, 'esil');
  assert.equal(await evaluate("document.querySelectorAll('.alternative-card').length"), 0, 'editing invalidates advice');
  assert.deepEqual(failures, []);
  console.log(JSON.stringify({ status: 'ok', verifiedReplacements: choices.length, mandatoryRisks: true, applyAndRecalculate: true, comparison: true, duplicateClick: 'blocked', retry: true, mobile: true, provider: 'mock', listeningServer: false }));
} finally {
  for (const waiting of pending.values()) clearTimeout(waiting.timer);
  socket?.close();
  if (browser.pid) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(browser.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    else browser.kill('SIGTERM');
    await delay(500);
  }
  assert(dirname(profile) === temporaryRoot && basename(profile).startsWith('akim-recommendations-'));
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
