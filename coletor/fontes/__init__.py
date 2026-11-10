"""Fontes de dados do coletor. Cada uma é independente: se uma falhar, as outras seguem."""

from . import cbf, espn, fixturedownload, globo, livescore, mlb, nhl, openfootball, openligadb, s365, thesportsdb

# Ordem de confiança para desempate de placar (a primeira ganha).
SECUNDARIAS = {
    "365scores": s365,
    "livescore": livescore,
    "ge": globo,
    "nhl": nhl,
    "mlb": mlb,
    "openligadb": openligadb,
    "thesportsdb": thesportsdb,
    "fixturedownload": fixturedownload,
    "openfootball": openfootball,
    "cbf": cbf,
}
PRIORIDADE = ["espn", *SECUNDARIAS]
NOMES = {"espn": espn.NOME, **{k: m.NOME for k, m in SECUNDARIAS.items()}}
# Fontes que também dão classificação (além da ESPN)
TABELAS = {"ge": globo, "cbf": cbf}

# Fontes de calendário: datas podem estar desatualizadas (remarcações). Elas só
# confirmam jogos que outra fonte já tem; nunca criam um jogo sozinhas.
SO_CONFIRMAM = {"openfootball", "fixturedownload", "thesportsdb"}
TOLERANCIA_DIAS = {"openfootball": 10, "fixturedownload": 10, "thesportsdb": 2}
