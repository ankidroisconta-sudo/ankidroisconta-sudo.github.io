// Ligas publicadas pela API. Para adicionar uma liga, inclua uma linha aqui.
// `sport` e `league` são os códigos usados pela ESPN nas URLs públicas.
// `details: true` busca também o detalhe completo (escalação, estatísticas,
// lances) de cada jogo ao vivo ou encerrado recentemente.
export const LEAGUES = [
  // Futebol — Brasil e América do Sul
  { id: 'brasileirao', name: 'Brasileirão Série A', sport: 'soccer', league: 'bra.1', details: true },
  { id: 'brasileirao-b', name: 'Brasileirão Série B', sport: 'soccer', league: 'bra.2', details: true },
  { id: 'copa-do-brasil', name: 'Copa do Brasil', sport: 'soccer', league: 'bra.copa_do_brazil', details: true },
  { id: 'libertadores', name: 'Copa Libertadores', sport: 'soccer', league: 'conmebol.libertadores', details: true },
  { id: 'sul-americana', name: 'Copa Sul-Americana', sport: 'soccer', league: 'conmebol.sudamericana', details: true },

  // Futebol — Europa e seleções
  { id: 'champions-league', name: 'UEFA Champions League', sport: 'soccer', league: 'uefa.champions', details: true },
  { id: 'premier-league', name: 'Premier League', sport: 'soccer', league: 'eng.1', details: true },
  { id: 'la-liga', name: 'La Liga', sport: 'soccer', league: 'esp.1', details: true },
  { id: 'serie-a-italia', name: 'Serie A (Itália)', sport: 'soccer', league: 'ita.1', details: true },
  { id: 'bundesliga', name: 'Bundesliga', sport: 'soccer', league: 'ger.1', details: true },
  { id: 'ligue-1', name: 'Ligue 1', sport: 'soccer', league: 'fra.1', details: true },
  { id: 'liga-portugal', name: 'Liga Portugal', sport: 'soccer', league: 'por.1', details: true },
  { id: 'mls', name: 'MLS', sport: 'soccer', league: 'usa.1', details: false },

  // Esportes americanos
  { id: 'nba', name: 'NBA', sport: 'basketball', league: 'nba', details: false },
  { id: 'nfl', name: 'NFL', sport: 'football', league: 'nfl', details: false },
  { id: 'mlb', name: 'MLB', sport: 'baseball', league: 'mlb', details: false },
  { id: 'nhl', name: 'NHL', sport: 'hockey', league: 'nhl', details: false },
];
