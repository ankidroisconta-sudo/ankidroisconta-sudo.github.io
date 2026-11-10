#!/usr/bin/env node
// Busca dados de jogos reais nos endpoints públicos da ESPN e gera arquivos
// JSON estáticos em <saída>/api/v1, que o GitHub Pages publica como API.
//
// Uso: node scripts/sports-api/build.mjs [diretório-de-saída]   (padrão: _site)
// Variáveis opcionais:
//   SITE_URL      URL pública do site, usada para reaproveitar o último dado
//                 publicado quando a ESPN falhar para uma liga.
//   DAYS_BACK     dias anteriores a incluir em games.json (padrão 3)
//   DAYS_AHEAD    dias seguintes a incluir em games.json (padrão 7)
//   MAX_DETAILS   limite de jogos com detalhe completo por execução (padrão 120)

import { mkdir, writeFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { LEAGUES } from './leagues.mjs';
import {
  normalizeScoreboard,
  normalizeStandings,
  normalizeTeams,
  normalizeSummary,
} from './normalize.mjs';

const OUT = join(process.argv[2] ?? '_site', 'api', 'v1');
const SITE_URL = (process.env.SITE_URL ?? '').replace(/\/$/, '');
const DAYS_BACK = Number(process.env.DAYS_BACK ?? 3);
const DAYS_AHEAD = Number(process.env.DAYS_AHEAD ?? 7);
const MAX_DETAILS = Number(process.env.MAX_DETAILS ?? 120);
const TZ = 'America/Sao_Paulo';

const SITE_API = 'https://site.api.espn.com/apis/site/v2/sports';
const STANDINGS_API = 'https://site.api.espn.com/apis/v2/sports';

const generatedAt = new Date().toISOString();
const problems = [];

async function getJson(url, { retries = 2, timeoutMs = 20000 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { 'User-Agent': 'sports-json-api/1.0', Accept: 'application/json' },
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      lastErr = err;
      if (attempt < retries) await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt));
    }
  }
  throw new Error(`${url}: ${lastErr?.message ?? lastErr}`);
}

// Último arquivo publicado, para não apagar dados quando a ESPN falhar.
async function previous(path) {
  if (!SITE_URL) return null;
  try {
    return await getJson(`${SITE_URL}/api/v1/${path}`, { retries: 0, timeoutMs: 10000 });
  } catch {
    return null;
  }
}

async function write(path, data) {
  const file = join(OUT, path);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, JSON.stringify(data));
}

const envelope = (extra, data) => ({ generatedAt, source: 'ESPN', ...extra, data });

function ymd(date) {
  // Data no fuso de Brasília, formato AAAAMMDD
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(date)
      .map((x) => [x.type, x.value]),
  );
  return `${p.year}${p.month}${p.day}`;
}

const shift = (days) => new Date(Date.now() + days * 86400000);
const today = ymd(new Date());

// Executa tarefas assíncronas com concorrência limitada.
async function pool(items, size, fn) {
  const results = new Array(items.length);
  let i = 0;
  await Promise.all(
    Array.from({ length: Math.min(size, items.length) }, async () => {
      while (i < items.length) {
        const idx = i++;
        results[idx] = await fn(items[idx], idx);
      }
    }),
  );
  return results;
}

async function withFallback(label, path, fn) {
  try {
    const data = await fn();
    await write(path, data);
    return { ok: true, data };
  } catch (err) {
    problems.push(`${label}: ${err.message}`);
    const old = await previous(path);
    if (old) {
      await write(path, { ...old, stale: true });
      return { ok: false, data: old };
    }
    return { ok: false, data: null };
  }
}

async function buildLeague(l) {
  const meta = { league: { id: l.id, name: l.name, sport: l.sport } };
  const base = `${SITE_API}/${l.sport}/${l.league}`;

  const games = await withFallback(`${l.id} jogos`, `${l.id}/games.json`, async () => {
    // A ESPN recusa intervalos de datas (AAAAMMDD-AAAAMMDD) com erro 400,
    // mas aceita um mês inteiro (AAAAMM). Busca os meses da janela e filtra.
    const from = ymd(shift(-DAYS_BACK));
    const to = ymd(shift(DAYS_AHEAD));
    const months = [...new Set([from.slice(0, 6), to.slice(0, 6)])];
    const seen = new Map();
    for (const m of months) {
      const json = await getJson(`${base}/scoreboard?dates=${m}&limit=500`);
      for (const g of normalizeScoreboard(json, l.id)) seen.set(g.id, g);
    }
    const list = [...seen.values()]
      .filter((g) => g.date && ymd(new Date(g.date)) >= from && ymd(new Date(g.date)) <= to)
      .sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''));
    return envelope({ ...meta, range: `${from}-${to}` }, list);
  });

  const all = games.data?.data ?? [];
  const todayList = all.filter((g) => g.date && ymd(new Date(g.date)) === today);
  await write(`${l.id}/today.json`, envelope({ ...meta, date: today }, todayList));
  await write(`${l.id}/live.json`, envelope(meta, all.filter((g) => g.status?.state === 'in')));

  const standings = await withFallback(`${l.id} classificação`, `${l.id}/standings.json`, async () =>
    envelope(meta, normalizeStandings(await getJson(`${STANDINGS_API}/${l.sport}/${l.league}/standings`))),
  );

  const teams = await withFallback(`${l.id} times`, `${l.id}/teams.json`, async () =>
    envelope(meta, normalizeTeams(await getJson(`${base}/teams`))),
  );

  return {
    l,
    games: all,
    ok: { games: games.ok, standings: standings.ok, teams: teams.ok },
  };
}

async function buildDetails(results) {
  // Detalhe completo para jogos ao vivo e jogos de hoje/ontem já encerrados.
  const yesterday = ymd(shift(-1));
  const wanted = [];
  for (const { l, games } of results) {
    for (const g of games) {
      const day = g.date ? ymd(new Date(g.date)) : null;
      const live = g.status?.state === 'in';
      const recent = g.status?.state === 'post' && (day === today || day === yesterday);
      const upcomingToday = g.status?.state === 'pre' && day === today;
      if (live || (l.details && (recent || upcomingToday))) wanted.push({ l, g, live });
    }
  }
  wanted.sort((a, b) => Number(b.live) - Number(a.live)); // ao vivo primeiro
  const chosen = wanted.slice(0, MAX_DETAILS);
  if (wanted.length > chosen.length) problems.push(`detalhes limitados a ${MAX_DETAILS} de ${wanted.length} jogos`);

  await pool(chosen, 6, async ({ l, g }) => {
    const path = `games/${g.id}.json`;
    await withFallback(`jogo ${g.id}`, path, async () => {
      const json = await getJson(`${SITE_API}/${l.sport}/${l.league}/summary?event=${g.id}`);
      return envelope({ league: { id: l.id, name: l.name, sport: l.sport } }, normalizeSummary(json, g));
    });
  });
  return chosen.map(({ g }) => g.id);
}

async function main() {
  const results = await pool(LEAGUES, 4, buildLeague);
  const detailed = new Set(await buildDetails(results));

  const allGames = results.flatMap((r) =>
    r.games.map((g) => ({ ...g, detailUrl: detailed.has(g.id) ? `games/${g.id}.json` : null })),
  );
  const byDate = (a, b) => (a.date ?? '').localeCompare(b.date ?? '');

  await write('live.json', envelope({}, allGames.filter((g) => g.status?.state === 'in').sort(byDate)));
  await write(
    'today.json',
    envelope({ date: today }, allGames.filter((g) => g.date && ymd(new Date(g.date)) === today).sort(byDate)),
  );

  const leagues = results.map(({ l, games, ok }) => ({
    id: l.id,
    name: l.name,
    sport: l.sport,
    espnCode: l.league,
    games: games.length,
    live: games.filter((g) => g.status?.state === 'in').length,
    ok,
    endpoints: {
      games: `${l.id}/games.json`,
      today: `${l.id}/today.json`,
      live: `${l.id}/live.json`,
      standings: `${l.id}/standings.json`,
      teams: `${l.id}/teams.json`,
    },
  }));
  await write('leagues.json', envelope({}, leagues));

  await write('status.json', {
    generatedAt,
    timezone: TZ,
    leagues: leagues.length,
    games: allGames.length,
    live: allGames.filter((g) => g.status?.state === 'in').length,
    detailedGames: detailed.size,
    problems,
  });

  console.log(
    `OK: ${leagues.length} ligas, ${allGames.length} jogos, ${detailed.size} detalhados, ${problems.length} problemas`,
  );
  for (const p of problems) console.warn(`  aviso: ${p}`);

  // Falha a execução só se nenhuma liga trouxe jogos novos (ex.: ESPN fora do ar).
  if (!results.some((r) => r.ok.games)) {
    console.error('Nenhuma liga atualizada; mantendo a versão publicada.');
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
