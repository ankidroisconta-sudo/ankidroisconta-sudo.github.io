"""FixtureDownload: calendário e resultados das principais ligas."""

from datetime import timedelta

from .base import FonteIndisponivel, baixar, jogo_simples

NOME = "FixtureDownload"
API = "https://fixturedownload.com/feed/json"
# liga -> (prefixo do arquivo, temporada no ano civil?)
COBERTURA = {
    "premier-league": ("epl", False), "la-liga": ("la-liga", False), "serie-a-italia": ("serie-a", False),
    "bundesliga": ("bundesliga", False), "ligue-1": ("ligue-1", False),
    "champions-league": ("champions-league", False), "mls": ("mls", True),
}


def jogos(ligas, hoje):
    ini, fim = (hoje - timedelta(days=30)).strftime("%Y-%m-%d"), (hoje + timedelta(days=14)).strftime("%Y-%m-%d")
    saida = []
    for l in ligas:
        if l["id"] not in COBERTURA:
            continue
        nome, civil = COBERTURA[l["id"]]
        ano = hoje.year if civil or hoje.month >= 7 else hoje.year - 1
        try:
            dados = baixar(f"{API}/{nome}-{ano}")
        except FonteIndisponivel:
            continue
        for m in dados if isinstance(dados, list) else []:
            data = (m.get("DateUtc") or "").replace(" ", "T")[:16] + "Z"
            if not (ini <= data[:10] <= fim):
                continue
            pc, pf = m.get("HomeTeamScore"), m.get("AwayTeamScore")
            saida.append(jogo_simples(
                "fixturedownload", l["id"], f"{nome}-{ano}-{m.get('MatchNumber')}", data,
                m.get("HomeTeam"), m.get("AwayTeam"), pc, pf, "encerrado" if pc is not None else "agendado",
            ))
    return saida
