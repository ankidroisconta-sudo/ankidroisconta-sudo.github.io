// Converte as respostas da ESPN para um formato estável e enxuto.
// Todas as funções toleram campos ausentes: a ESPN muda o formato sem aviso.

const num = (v) => {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const STATUS_PT = { pre: 'agendado', in: 'ao_vivo', post: 'encerrado' };

function normalizeTeam(t = {}) {
  return {
    id: t.id ?? null,
    name: t.displayName ?? t.name ?? null,
    shortName: t.shortDisplayName ?? t.abbreviation ?? null,
    abbreviation: t.abbreviation ?? null,
    logo: t.logo ?? t.logos?.[0]?.href ?? null,
    color: t.color ? `#${t.color}` : null,
  };
}

function normalizeCompetitor(c = {}) {
  return {
    team: normalizeTeam(c.team),
    homeAway: c.homeAway ?? null,
    score: num(c.score?.value ?? c.score),
    winner: c.winner ?? null,
    record: c.records?.[0]?.summary ?? null,
    form: c.form ?? null,
    shootoutScore: num(c.shootoutScore),
    linescores: (c.linescores ?? []).map((l) => num(l.value ?? l.displayValue)),
    statistics: Object.fromEntries(
      (c.statistics ?? []).map((s) => [s.name ?? s.abbreviation, s.displayValue ?? null]),
    ),
  };
}

function normalizeDetail(d = {}) {
  return {
    type: d.type?.text ?? null,
    minute: d.clock?.displayValue ?? null,
    teamId: d.team?.id ?? null,
    scoringPlay: Boolean(d.scoringPlay),
    yellowCard: Boolean(d.yellowCard),
    redCard: Boolean(d.redCard),
    penalty: Boolean(d.penaltyKick),
    ownGoal: Boolean(d.ownGoal),
    athletes: (d.athletesInvolved ?? []).map((a) => a.displayName).filter(Boolean),
  };
}

export function normalizeStatus(s = {}) {
  const state = s.type?.state ?? null;
  return {
    state, // pre | in | post
    statePt: STATUS_PT[state] ?? null,
    completed: Boolean(s.type?.completed),
    description: s.type?.description ?? null,
    detail: s.type?.detail ?? null,
    shortDetail: s.type?.shortDetail ?? null,
    clock: s.displayClock ?? null,
    period: num(s.period),
  };
}

export function normalizeEvent(e = {}, leagueId) {
  const comp = e.competitions?.[0] ?? {};
  const competitors = (comp.competitors ?? []).map(normalizeCompetitor);
  const home = competitors.find((c) => c.homeAway === 'home') ?? competitors[0] ?? null;
  const away = competitors.find((c) => c.homeAway === 'away') ?? competitors[1] ?? null;
  const venue = comp.venue ?? {};
  return {
    id: e.id ?? null,
    league: leagueId,
    date: e.date ?? comp.date ?? null,
    name: e.name ?? null,
    shortName: e.shortName ?? null,
    season: e.season?.year ?? null,
    seasonType: e.season?.slug ?? null,
    week: e.week?.number ?? null,
    round: comp.notes?.[0]?.headline ?? null,
    status: normalizeStatus(comp.status ?? e.status),
    home,
    away,
    venue: venue.fullName
      ? {
          name: venue.fullName,
          city: venue.address?.city ?? null,
          country: venue.address?.country ?? null,
        }
      : null,
    attendance: num(comp.attendance),
    broadcasts: (comp.broadcasts ?? []).flatMap((b) => b.names ?? []),
    events: (comp.details ?? []).map(normalizeDetail),
    odds: comp.odds?.[0]
      ? {
          provider: comp.odds[0].provider?.name ?? null,
          details: comp.odds[0].details ?? null,
          overUnder: num(comp.odds[0].overUnder),
          spread: num(comp.odds[0].spread),
          homeMoneyLine: num(comp.odds[0].homeTeamOdds?.moneyLine),
          awayMoneyLine: num(comp.odds[0].awayTeamOdds?.moneyLine),
          drawMoneyLine: num(comp.odds[0].drawOdds?.moneyLine),
        }
      : null,
    link: e.links?.find((l) => l.rel?.includes('summary'))?.href ?? e.links?.[0]?.href ?? null,
  };
}

export function normalizeScoreboard(json = {}, leagueId) {
  return (json.events ?? []).map((e) => normalizeEvent(e, leagueId));
}

function statMap(stats = []) {
  const out = {};
  for (const s of stats) {
    const key = s.name ?? s.abbreviation ?? s.type;
    if (!key) continue;
    out[key] = s.value !== undefined && s.value !== null ? s.value : (s.displayValue ?? null);
  }
  return out;
}

export function normalizeStandings(json = {}) {
  // A ESPN devolve as tabelas em `children` (grupos/conferências)
  // ou diretamente em `standings` quando há uma tabela única.
  const groups = json.children?.length ? json.children : [json];
  return groups
    .map((g) => ({
      name: g.name ?? json.name ?? null,
      abbreviation: g.abbreviation ?? null,
      entries: (g.standings?.entries ?? []).map((en, i) => {
        const stats = statMap(en.stats);
        return {
          position: num(stats.rank) ?? i + 1,
          team: normalizeTeam(en.team),
          note: en.note?.description ?? null,
          noteColor: en.note?.color ?? null,
          points: num(stats.points),
          played: num(stats.gamesPlayed),
          wins: num(stats.wins),
          draws: num(stats.ties),
          losses: num(stats.losses),
          goalsFor: num(stats.pointsFor),
          goalsAgainst: num(stats.pointsAgainst),
          goalDifference: num(stats.pointDifferential),
          winPercent: num(stats.winPercent),
          gamesBehind: num(stats.gamesBehind),
          streak: stats.streak ?? null,
          stats,
        };
      }),
    }))
    .filter((g) => g.entries.length > 0);
}

export function normalizeTeams(json = {}) {
  const teams = json.sports?.[0]?.leagues?.[0]?.teams ?? [];
  return teams.map(({ team = {} }) => ({
    ...normalizeTeam(team),
    location: team.location ?? null,
    nickname: team.nickname ?? null,
    alternateColor: team.alternateColor ? `#${team.alternateColor}` : null,
    link: team.links?.[0]?.href ?? null,
  }));
}

export function normalizeSummary(json = {}, base) {
  const rosters = (json.rosters ?? []).map((r) => ({
    team: normalizeTeam(r.team),
    homeAway: r.homeAway ?? null,
    formation: r.formation ?? null,
    players: (r.roster ?? []).map((p) => ({
      name: p.athlete?.displayName ?? null,
      jersey: p.jersey ?? null,
      position: p.position?.abbreviation ?? null,
      starter: Boolean(p.starter),
      subbedIn: Boolean(p.subbedIn),
      subbedOut: Boolean(p.subbedOut),
    })),
  }));

  const teamStats = (json.boxscore?.teams ?? []).map((t) => ({
    team: normalizeTeam(t.team),
    statistics: Object.fromEntries(
      (t.statistics ?? []).map((s) => [s.name ?? s.label, s.displayValue ?? null]),
    ),
  }));

  const keyEvents = (json.keyEvents ?? []).map((k) => ({
    type: k.type?.text ?? null,
    minute: k.clock?.displayValue ?? null,
    period: num(k.period?.number),
    team: k.team?.displayName ?? null,
    text: k.text ?? k.shortText ?? null,
    athletes: (k.participants ?? []).map((p) => p.athlete?.displayName).filter(Boolean),
    scoringPlay: Boolean(k.scoringPlay),
  }));

  const info = json.gameInfo ?? {};
  return {
    ...base,
    venue: base?.venue ?? (info.venue?.fullName ? { name: info.venue.fullName, city: info.venue.address?.city ?? null, country: info.venue.address?.country ?? null } : null),
    attendance: base?.attendance ?? num(info.attendance),
    officials: (info.officials ?? []).map((o) => o.displayName).filter(Boolean),
    teamStats,
    lineups: rosters,
    keyEvents,
    headToHead: (json.headToHeadGames?.[0]?.events ?? []).map((g) => ({
      id: g.id ?? null,
      date: g.gameDate ?? null,
      score: g.score ?? null,
      result: g.gameResult ?? null,
      homeTeamId: g.homeTeamId ?? null,
      awayTeamId: g.awayTeamId ?? null,
    })),
    news: (json.news?.articles ?? []).slice(0, 5).map((a) => ({
      headline: a.headline ?? null,
      description: a.description ?? null,
      published: a.published ?? null,
      link: a.links?.web?.href ?? null,
    })),
  };
}
