// Roda o build inteiro com a rede simulada, para checar os arquivos gerados.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const here = new URL('.', import.meta.url).pathname;

function run(mockSource) {
  const dir = mkdtempSync(join(tmpdir(), 'sports-api-'));
  const mock = join(dir, 'mock.mjs');
  writeFileSync(mock, mockSource);
  const r = spawnSync(process.execPath, ['--import', mock, join(here, 'build.mjs'), dir], {
    encoding: 'utf8',
    env: { ...process.env, SITE_URL: '' },
  });
  return { dir, ...r, read: (p) => JSON.parse(readFileSync(join(dir, 'api', 'v1', p), 'utf8')) };
}

test('gera todos os arquivos com dados simulados', () => {
  const now = new Date().toISOString();
  const r = run(`
    globalThis.fetch = async (url) => {
      let body = {};
      if (url.includes('/scoreboard')) {
        body = url.includes('bra.1') ? { events: [{ id: '9', date: '${now}', competitions: [{
          status: { type: { state: 'in' } },
          competitors: [{ homeAway: 'home', score: '1', team: { id: '1', displayName: 'A' } },
                        { homeAway: 'away', score: '0', team: { id: '2', displayName: 'B' } }] }] }] } : { events: [] };
      } else if (url.includes('/summary')) {
        body = { gameInfo: { officials: [{ displayName: 'Juiz' }] } };
      } else if (url.includes('/standings')) {
        body = { standings: { entries: [{ team: { id: '1' }, stats: [{ name: 'points', value: 3 }] }] } };
      } else if (url.includes('/teams')) {
        body = { sports: [{ leagues: [{ teams: [{ team: { id: '1', displayName: 'A' } }] }] }] };
      }
      return new Response(JSON.stringify(body), { status: 200 });
    };
  `);
  assert.equal(r.status, 0, r.stderr);
  const status = r.read('status.json');
  assert.equal(status.live, 1);
  assert.deepEqual(status.problems, []);
  assert.equal(r.read('live.json').data[0].detailUrl, 'games/9.json');
  assert.equal(r.read('today.json').data.length, 1);
  assert.equal(r.read('brasileirao/live.json').data.length, 1);
  assert.equal(r.read('brasileirao/standings.json').data[0].entries[0].points, 3);
  assert.deepEqual(r.read('games/9.json').data.officials, ['Juiz']);
  assert.ok(r.read('leagues.json').data.length > 10);
});

test('falha geral da ESPN encerra com erro', () => {
  const r = run(`globalThis.fetch = async () => new Response('x', { status: 503 }); globalThis.setTimeout = (f) => f();`);
  assert.equal(r.status, 1);
  assert.ok(existsSync(join(r.dir, 'api', 'v1', 'status.json')));
});
