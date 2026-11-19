#!/usr/bin/env node
// One-shot Linux/runtime integration test; every child is stopped in finally.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, mkdir, writeFile, rm, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createServer } from 'node:net';

const runtime = resolve(process.argv[2] ?? 'android/runtime');
const temporary = await mkdtemp(join(tmpdir(), 'terminator-runtime-'));
let child;
let log = '';
const passed = [];
async function freePort() {
  const reservation = createServer();
  reservation.listen(0, '0.0.0.0');
  await once(reservation, 'listening');
  const port = reservation.address().port;
  await new Promise((done, fail) => reservation.close(error => error ? fail(error) : done()));
  return port;
}
try {
  const home = join(temporary, 'home');
  await mkdir(home);
  const port = await freePort();
  const webhookPort = await freePort();
  child = spawn(process.execPath, ['--max-old-space-size=768', join(runtime, 'node_modules/openmausbot/dist-server/index.js')], {
    env: {
      PATH: process.env.PATH,
      HOME: home,
      LANG: 'C.UTF-8',
      OMB_DATA_DIR: join(temporary, 'workspace'),
      OMB_STATIC_DIR: join(runtime, 'node_modules/openmausbot/dist'),
      OMB_PORT: String(port),
      OMB_WEBHOOK_PORT: String(webhookPort),
      OMB_LAN: '1', // The test server binds 0.0.0.0, not a preview-breaking localhost-only interface.
      OMB_LOOPBACK_TRUST: 'service',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await new Promise((done, fail) => {
    const timeout = setTimeout(() => fail(Error('Upstream readiness timeout')), 60000);
    const stopped = code => { clearTimeout(timeout); fail(Error(`Upstream exited before readiness: ${code}`)); };
    const failed = error => { clearTimeout(timeout); fail(error); };
    const onLog = chunk => {
      log = (log + chunk.toString()).slice(-20000);
      if (log.includes('openmausbot server on http://')) {
        clearTimeout(timeout);
        child.off('exit', stopped);
        child.off('error', failed);
        done();
      }
    };
    child.stdout.on('data', onLog);
    child.stderr.on('data', onLog);
    child.once('exit', stopped);
    child.once('error', failed);
  });
  const base = `http://127.0.0.1:${port}`;
  const get = (path, headers) => fetch(base + path, { headers, signal: AbortSignal.timeout(10000), redirect: 'error' });
  const page = await get('/');
  assert.equal(page.status, 200);
  assert.match(await page.text(), /<html/);
  passed.push('Original web UI served');
  const health = await (await get('/api/health')).json();
  assert.equal(health.app, 'openmausbot');
  assert.equal(health.version, '0.1.169');
  assert.equal(health.static, true);
  passed.push('Original server health/version/static assets');
  const environment = await (await get('/.well-known/openmausbot/environment')).json();
  assert.equal(environment.version, '0.1.169');
  assert.equal(environment.capabilities.remoteSessions, true);
  passed.push('Environment descriptor');
  const manifest = await (await get('/manifest.webmanifest')).json();
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.start_url, '/');
  passed.push('Original phone web-app manifest');
  for (const headers of [undefined, { 'x-openmausbot-cli': '1' }, { origin: 'https://example.invalid' }]) {
    const response = await get('/api/config', headers);
    assert.ok([401, 403].includes(response.status), `Unauthenticated config returned ${response.status}`);
  }
  passed.push('Service trust rejects anonymous, forged-local-CLI and foreign-origin config reads');

  const fixture = join(temporary, 'static-fixture');
  await mkdir(fixture);
  await writeFile(join(fixture, 'package.json'), JSON.stringify({ name: 'terminator-static-fixture', version: '1.0.0', type: 'module', main: 'index.js' }));
  const sentinel = join(fixture, 'MUST_NOT_EXECUTE');
  await writeFile(join(fixture, 'index.js'), 'import { writeFileSync } from "node:fs";\nwriteFileSync(new URL("./MUST_NOT_EXECUTE", import.meta.url), "bad");\nexport const answer = 42;\n');
  const analysis = spawnSync(process.execPath, [join(runtime, 'node_modules/rea-agents/scripts/rea.mjs'),
    'analyze-javascript-application', fixture, '--json'], {
    env: { PATH: process.env.PATH, HOME: home, LANG: 'C.UTF-8' },
    encoding: 'utf8', timeout: 60000, maxBuffer: 8 * 1024 * 1024,
  });
  assert.equal(analysis.status, 0, analysis.stderr.slice(-2000));
  const evidence = JSON.parse(analysis.stdout);
  assert.equal(evidence.operation, 'analyze_javascript_application');
  assert.ok(evidence.evidence_id);
  let executed = false;
  try { await access(sentinel); executed = true; } catch (error) { if (error.code !== 'ENOENT') throw error; }
  assert.equal(executed, false, 'Static analysis must not execute the target');
  passed.push('REA static analysis returned Evidence without executing the fixture');
  console.log(JSON.stringify({ passed, executionHost: { platform: process.platform, architecture: process.arch },
    androidParity: 'NOT_CERTIFIED', paidProviderRequestsTested: false }, null, 2));
} catch (error) {
  console.error(error);
  console.error('Bounded credential-free upstream test log:\n' + log);
  process.exitCode = 1;
} finally {
  if (child && child.exitCode === null && child.signalCode === null) {
    const exited = once(child, 'exit');
    const force = setTimeout(() => child.kill('SIGKILL'), 10000);
    child.kill('SIGTERM');
    await exited;
    clearTimeout(force);
  }
  await rm(temporary, { recursive: true, force: true });
}
