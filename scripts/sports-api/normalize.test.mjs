import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeScoreboard, normalizeStandings, normalizeTeams, normalizeSummary } from './normalize.mjs';

const scoreboard = {
  events: [
    {
      id: '701',
      date: '2026-11-09T22:00Z',
      name: 'Palmeiras at Flamengo',
      shortName: 'PAL @ FLA',
      season: { year: 2026, slug: 'regular-season' },
      links: [{ rel: ['summary', 'desktop'], href: 'https://espn.com/x' }],
      competitions: [
        {
          attendance: 61000,
          venue: { fullName: 'Maracanã', address: { city: 'Rio de Janeiro', country: 'Brazil' } },
          status: {
            displayClock: "67'",
            period: 2,
            type: { state: 'in', completed: false, description: 'Second Half', detail: "67'", shortDetail: "67'" },
          },
          competitors: [
            {
              homeAway: 'home',
              score: '2',
              form: 'WWDLW',
              records: [{ summary: '20-8-5' }],
              team: { id: '819', displayName: 'Flamengo', abbreviation: 'FLA', logo: 'f.png', color: 'c00' },
              statistics: [{ name: 'possessionPct', displayValue: '58.2' }],
            },
            {
              homeAway: 'away',
              score: '1',
              team: { id: '2029', displayName: 'Palmeiras', abbreviation: 'PAL' },
            },
          ],
          details: [
            {
              type: { text: 'Goal' },
              clock: { displayValue: "12'" },
              team: { id: '819' },
              scoringPlay: true,
              athletesInvolved: [{ displayName: 'Pedro' }],
            },
          ],
          broadcasts: [{ names: ['Globo', 'Premiere'] }],
        },
      ],
    },
  ],
};

test('normaliza placar ao vivo', () => {
  const [g] = normalizeScoreboard(scoreboard, 'brasileirao');
  assert.equal(g.id, '701');
  assert.equal(g.status.state, 'in');
  assert.equal(g.status.statePt, 'ao_vivo');
  assert.equal(g.home.team.name, 'Flamengo');
  assert.equal(g.home.score, 2);
  assert.equal(g.away.score, 1);
  assert.equal(g.home.team.color, '#c00');
  assert.equal(g.home.statistics.possessionPct, '58.2');
  assert.equal(g.venue.city, 'Rio de Janeiro');
  assert.deepEqual(g.broadcasts, ['Globo', 'Premiere']);
  assert.deepEqual(g.events[0].athletes, ['Pedro']);
  assert.equal(g.events[0].scoringPlay, true);
  assert.equal(g.link, 'https://espn.com/x');
});

test('jogo agendado sem placar não quebra', () => {
  const [g] = normalizeScoreboard(
    { events: [{ id: '1', competitions: [{ competitors: [{ homeAway: 'home', team: {} }, { homeAway: 'away', team: {} }], status: { type: { state: 'pre' } } }] }] },
    'x',
  );
  assert.equal(g.home.score, null);
  assert.equal(g.status.statePt, 'agendado');
  assert.equal(g.venue, null);
  assert.equal(g.odds, null);
});

test('resposta vazia vira lista vazia', () => {
  assert.deepEqual(normalizeScoreboard({}, 'x'), []);
  assert.deepEqual(normalizeStandings({}), []);
  assert.deepEqual(normalizeTeams({}), []);
});

const entry = (name, rank, pts) => ({
  team: { id: name, displayName: name, logos: [{ href: `${name}.png` }] },
  note: rank === 1 ? { description: 'Libertadores', color: '#0f0' } : undefined,
  stats: [
    { name: 'rank', value: rank },
    { name: 'points', value: pts },
    { name: 'gamesPlayed', value: 33 },
    { name: 'wins', value: 20 },
    { name: 'ties', value: 8 },
    { name: 'losses', value: 5 },
    { name: 'pointsFor', value: 60 },
    { name: 'pointsAgainst', value: 25 },
    { name: 'pointDifferential', value: 35 },
  ],
});

test('classificação com tabela única', () => {
  const [g] = normalizeStandings({ name: 'Série A', standings: { entries: [entry('FLA', 1, 68), entry('PAL', 2, 65)] } });
  assert.equal(g.entries.length, 2);
  assert.equal(g.entries[0].points, 68);
  assert.equal(g.entries[0].draws, 8);
  assert.equal(g.entries[0].goalDifference, 35);
  assert.equal(g.entries[0].note, 'Libertadores');
  assert.equal(g.entries[0].team.logo, 'FLA.png');
});

test('classificação com grupos', () => {
  const groups = normalizeStandings({
    children: [
      { name: 'Grupo A', standings: { entries: [entry('A', 1, 10)] } },
      { name: 'Grupo B', standings: { entries: [entry('B', 1, 9)] } },
    ],
  });
  assert.deepEqual(groups.map((g) => g.name), ['Grupo A', 'Grupo B']);
});

test('times', () => {
  const [t] = normalizeTeams({ sports: [{ leagues: [{ teams: [{ team: { id: '1', displayName: 'Flamengo', location: 'Rio' } }] }] }] });
  assert.equal(t.name, 'Flamengo');
  assert.equal(t.location, 'Rio');
});

test('detalhe do jogo com escalação, estatísticas e lances', () => {
  const [base] = normalizeScoreboard(scoreboard, 'brasileirao');
  const d = normalizeSummary(
    {
      rosters: [
        {
          homeAway: 'home',
          formation: '4-3-3',
          team: { id: '819', displayName: 'Flamengo' },
          roster: [{ athlete: { displayName: 'Rossi' }, jersey: '1', position: { abbreviation: 'G' }, starter: true }],
        },
      ],
      boxscore: { teams: [{ team: { id: '819' }, statistics: [{ name: 'totalShots', displayValue: '14' }] }] },
      keyEvents: [{ type: { text: 'Yellow Card' }, clock: { displayValue: "30'" }, participants: [{ athlete: { displayName: 'Gerson' } }] }],
      gameInfo: { officials: [{ displayName: 'Anderson Daronco' }] },
    },
    base,
  );
  assert.equal(d.id, '701');
  assert.equal(d.lineups[0].formation, '4-3-3');
  assert.equal(d.lineups[0].players[0].starter, true);
  assert.equal(d.teamStats[0].statistics.totalShots, '14');
  assert.deepEqual(d.keyEvents[0].athletes, ['Gerson']);
  assert.deepEqual(d.officials, ['Anderson Daronco']);
  assert.equal(d.venue.name, 'Maracanã');
});
