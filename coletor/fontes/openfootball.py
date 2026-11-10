"""openfootball: resultados em domínio público, mantidos por voluntários (atualiza com algum atraso)."""

from datetime import timedelta

from .base import FonteIndisponivel, baixar, jogo_simples

NOME = "openfootball"
API = "https://raw.githubusercontent.com/openfootball/football.json/master"
# liga -> (arquivo, temporada no ano civil?)
COBERTURA = {
    "brasileirao": ("br.1", True), "premier-league": ("en.1", False), "la-liga": ("es.1", False),
    "serie-a-italia": ("it.1", False), "bundesliga": ("de.1", False), "ligue-1": ("fr.1", False),
    "liga-portugal": ("pt.1", False),
}


def jogos(ligas, hoje):
    ini, fim = (hoje - timedelta(days=30)).strftime("%Y-%m-%d"), (hoje + timedelta(days=14)).strftime("%Y-%m-%d")
    saida = []
    for l in ligas:
        if l["id"] not in COBERTURA:
            continue
        arq, civil = COBERTURA[l["id"]]
        a = hoje.year if civil or hoje.month >= 7 else hoje.year - 1
        temporada = str(a) if civil else f"{a}-{str(a + 1)[2:]}"
        try:
            dados = baixar(f"{API}/{temporada}/{arq}.json")
        except FonteIndisponivel:
            continue  # temporada ainda sem arquivo
        for i, m in enumerate(dados.get("matches") or []):
            dia = m.get("date") or ""
            if not (ini <= dia <= fim):
                continue
            ft = (m.get("score") or {}).get("ft") or [None, None]
            saida.append(jogo_simples(
                "openfootball", l["id"], f"{temporada}-{arq}-{i}", dia, m.get("team1"), m.get("team2"),
                ft[0], ft[1], "encerrado" if ft[0] is not None else "agendado",
            ))
    return saida
