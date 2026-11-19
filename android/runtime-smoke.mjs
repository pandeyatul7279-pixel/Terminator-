#!/usr/bin/env node
// Local, credential-free probes. Passing these is not Android feature certification.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
if (args.includes('--help')) {
  console.log('Usage: node android/runtime-smoke.mjs --runtime /path/to/runtime');
  process.exit(0);
}
if (args.length !== 2 || args[0] !== '--runtime') {
  console.error('Expected --runtime DIRECTORY');
  process.exit(2);
}
const runtime = resolve(args[1]);
const require = createRequire(join(runtime, 'package.json'));
const checks = [];
async function check(id, required, action) {
  try { checks.push({ id, required, status: 'pass', detail: await action() }); }
  catch (error) { checks.push({ id, required, status: 'fail', detail: String(error.message).slice(0, 700) }); }
}
const packageVersion = name => JSON.parse(readFileSync(join(runtime, 'node_modules', name, 'package.json'))).version;
function run(entry, argv) {
  const result = spawnSync(process.execPath, [entry, ...argv], { encoding: 'utf8', timeout: 30000, maxBuffer: 1024 * 1024 });
  if (result.error || result.status !== 0) throw result.error ?? new Error(result.stderr || `Exit ${result.status}`);
  return result.stdout.trim();
}
await check('node', true, () => {
  if (process.versions.node !== '24.22.1') throw Error(`Expected Node 24.22.1, found ${process.versions.node}`);
  return process.versions.node;
});
for (const [name, expected, entry] of [
  ['openmausbot', '0.1.169', 'cli.js'], ['rea-agents', '6.9.0', 'scripts/rea.mjs'],
]) {
  await check(name, true, () => {
    if (packageVersion(name) !== expected) throw Error(`Expected ${expected}`);
    const version = run(join(runtime, 'node_modules', name, entry), ['--version']);
    if (version !== expected) throw Error(`Unexpected CLI version: ${version}`);
    return `Original CLI ${version}`;
  });
}
await check('duckdb-native-binding', true, async () => {
  const api = require('@duckdb/node-api');
  const database = await api.DuckDBInstance.create(':memory:');
  let connection;
  try { connection = await database.connect(); await connection.run('SELECT 42 AS answer'); }
  finally { connection?.closeSync(); database.closeSync(); }
  return 'Native in-memory database opened; SELECT completed';
});
await check('resvg-native-binding', true, () => {
  const { Resvg } = require('@resvg/resvg-js');
  const png = new Resvg('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="red"/></svg>').render().asPng();
  if (!png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw Error('Not a PNG');
  return 'Native SVG-to-PNG render completed';
});
await check('1password-module', true, () => {
  require('@1password/sdk');
  return 'Module imported only; authentication/vault operations NOT tested';
});
await check('procps', true, () => {
  const result = spawnSync('ps', ['-eo', 'pid=,args='], { encoding: 'utf8', timeout: 5000, maxBuffer: 2 * 1024 * 1024 });
  if (result.error || result.status !== 0 || !result.stdout.trim()) throw Error('REA needs procps-compatible ps');
  return 'procps-compatible ps responds; no process details retained';
});
await check('frida-optional', false, () => {
  const reaRequire = createRequire(join(runtime, 'node_modules/rea-agents/package.json'));
  reaRequire.resolve('frida');
  return 'Package present only; Android process attachment NOT tested/authorised';
});
const ready = checks.filter(check => check.required).every(check => check.status === 'pass');
console.log(JSON.stringify({
  readyForDeviceTrial: ready,
  androidParity: 'NOT_CERTIFIED',
  executionHost: { platform: process.platform, architecture: process.arch, node: process.versions.node },
  checks,
  limitations: [
    'A Linux x64 pass is NOT an Android ARM64 pass.',
    'No provider calls, paid integrations, browser automation or native Android screen-control tests were performed.',
    'Optional Frida absence is a missing capability, not a successful all-features installation.',
    'PRoot is a compatibility userland, not a Docker/VM security boundary.',
  ],
}, null, 2));
process.exitCode = ready ? 0 : 1;
