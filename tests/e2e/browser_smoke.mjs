// Finite UI check using an installed Chromium browser and Node's native WebSocket.
// No npm packages, server or persistent browser profile are installed by this script.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const origin = new URL(process.argv[2] || 'http://127.0.0.1:8000');
assert(['http:', 'https:'].includes(origin.protocol), 'Use an HTTP(S) origin');
assert(!origin.username && !origin.password && origin.pathname === '/' && !origin.search && !origin.hash);
const executable = process.env.BROWSER_EXECUTABLE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const temporaryRoot = realpathSync(tmpdir());
const profile = mkdtempSync(join(temporaryRoot, 'akim-browser-'));
const browser = spawn(executable, [
  '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', 'about:blank',
], { windowsHide: true, stdio: 'ignore' });
let launchError;
browser.on('error', (error) => { launchError = error; });
let socket;
const deadline = Date.now() + 45000;
const pending = new Map();
let sequence = 0;
const failures = [];
const apiRequests = [];

async function until(check, description) {
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    if (await check()) return;
    await delay(100);
  }
  throw new Error(`Timeout: ${description}`);
}

function command(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 10000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!result.exceptionDetails, 'Browser evaluation failed');
  return result.result.value;
}

try {
  let port;
  await until(() => {
    try { port = Number(readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0]); return !!port; }
    catch { return false; }
  }, 'browser startup');
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(5000) })).json();
  const page = pages.find((entry) => entry.type === 'page');
  assert(page, 'Browser page missing');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Browser connection timeout')), 5000);
    socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
    socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Browser connection failed')); }, { once: true });
  });
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const waiting = pending.get(message.id);
      if (!waiting) return;
      clearTimeout(waiting.timer);
      pending.delete(message.id);
      if (message.error) waiting.reject(new Error(message.error.message));
      else waiting.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') failures.push('Uncaught browser exception');
    if (message.method === 'Network.loadingFailed' && !message.params.canceled) failures.push('Browser request failed');
    if (message.method === 'Network.requestWillBeSent' && message.params.type === 'Fetch') apiRequests.push(message.params.request.url);
    if (message.method === 'Network.responseReceived' && ['Fetch', 'Script', 'Stylesheet'].includes(message.params.type) && message.params.response.status >= 400) failures.push('API or asset HTTP error');
  });
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Network.enable');
  await command('Page.navigate', { url: origin.href });
  await until(() => evaluate("document.querySelectorAll('.decision').length === 5 && document.body.innerText.includes('52.56')"), 'initial catalog and baseline');
  await evaluate("document.querySelector('button').click()");
  await until(() => evaluate("document.body.innerText.includes('56.54') && document.body.innerText.includes('+3.99') && !document.querySelector('button').disabled"), 'PDF scenario');
  assert(await evaluate("document.querySelector('.notice')?.innerText.length > 0"), 'AI notice missing');
  await evaluate(`(() => {
    const select = document.querySelector('.decision').querySelectorAll('select')[1];
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(select, 'esil');
    select.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await until(() => evaluate("document.querySelector('.decision').querySelectorAll('select')[1].value === 'esil' && !document.querySelector('.notice')"), 'district selection');
  await evaluate("document.querySelector('button').click()");
  await until(() => evaluate("document.body.innerText.includes('55.30') && !document.querySelector('button').disabled"), 'alternative scenario');
  assert(apiRequests.length >= 5, 'Expected startup and analysis requests');
  assert(apiRequests.every((url) => new URL(url).origin === origin.origin), 'Frontend called a different API origin');
  assert.deepEqual(failures, []);
  console.log(JSON.stringify({ status: 'ok', browser: 'Chromium', baseline: '52.56', pdf: '56.54', schoolInEsil: '55.30', apiRequests: apiRequests.length, sameOrigin: true }));
} finally {
  for (const waiting of pending.values()) clearTimeout(waiting.timer);
  socket?.close();
  if (browser.pid) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(browser.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    else browser.kill('SIGTERM');
    await delay(500);
  }
  // Delete only the temporary profile created by this invocation.
  assert(dirname(profile) === temporaryRoot && basename(profile).startsWith('akim-browser-'));
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
