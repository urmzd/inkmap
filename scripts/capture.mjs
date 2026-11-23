// Capture the README demo images from a built viewer page.
//
//   node scripts/capture.mjs out/synthetic.html showcase
//
// Drives a real headless Chrome over the DevTools protocol: opens the page, turns to the
// first bare area, places the first sample design, and saves a light and a dark screenshot.
// No dependencies. Needs Node 22+ and Chrome (set CHROME to its path if it is not found).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [, , page, outDir = 'showcase'] = process.argv;
if (!page) { console.error('usage: node scripts/capture.mjs <viewer.html> [out-dir]'); process.exit(1); }
const chromePath = process.env.CHROME || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].find(existsSync);
if (!chromePath) { console.error('Chrome not found. Set CHROME to its path.'); process.exit(1); }

const port = 9300 + Math.floor(Math.random() * 500);
const profile = mkdtempSync(join(tmpdir(), 'inkmap-capture-'));
const chrome = spawn(chromePath, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--hide-scrollbars', '--enable-gpu', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let failed = false;
try {
  let targets;
  for (let i = 0; i < 60 && !targets; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(200); }
  }
  if (!targets) throw new Error('Chrome did not start');
  const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = new Map(); const errors = [];
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
    if (d.method === 'Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, (d) => (d.error ? rej(new Error(`${method}: ${d.error.message}`)) : res(d.result)));
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const run = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  const scheme = (value) => send('Emulation.setEmulatedMedia', { features: [
    { name: 'prefers-color-scheme', value }, { name: 'prefers-reduced-motion', value: 'reduce' }] });

  await send('Page.enable'); await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 750, deviceScaleFactor: 2, mobile: false });
  await scheme('light');
  await send('Page.navigate', { url: pathToFileURL(resolve(page)).href });
  for (let i = 0; i < 50 && !(await run('!!window.inkmap')); i++) await sleep(200);
  if (!(await run('!!window.inkmap'))) throw new Error('the viewer did not start (no window.inkmap)');

  // turn to the first bare area, place the first sample there, then step back to show the arm
  await run(`inkmap.goTo('z0')`);
  await run(`document.querySelector('.design .place').click()`);
  await run(`inkmap.select(null); inkmap.view.rad = 120; inkmap.view.pol = 1.5; inkmap.applyView()`);

  mkdirSync(outDir, { recursive: true });
  for (const mode of ['light', 'dark']) {
    await scheme(mode); await sleep(700);
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const file = join(outDir, `demo-${mode}.png`);
    writeFileSync(file, Buffer.from(shot.data, 'base64'));
    console.log('wrote', file);
  }
  if (errors.length) throw new Error('page errors: ' + errors.join('; '));
  ws.close();
} catch (e) {
  console.error('error:', e.message); failed = true;
} finally {
  chrome.kill(); await sleep(300); rmSync(profile, { recursive: true, force: true });
}
process.exit(failed ? 1 : 0);
