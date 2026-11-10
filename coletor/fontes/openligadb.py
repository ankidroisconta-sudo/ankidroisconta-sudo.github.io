"""OpenLigaDB: base de dados aberta e comunitária do futebol alemão."""

from datetime import datetime, timedelta

from .base import baixar, jogo_simples

NOME = "OpenLigaDB"
API = "https://api.openligadb.de"
COBERTURA = {"bundesliga": "bl1"}


def jogos(ligas, hoje):
    saida = []
    temporada = hoje.year if hoje.month >= 7 else hoje.year - 1
    ini, fim = (hoje - timedelta(days=30)).strftime("%Y-%m-%d"), (hoje + timedelta(days=14)).strftime("%Y-%m-%d")
    for l in ligas:
        if l["id"] not in COBERTURA:
            continue
        for m in baixar(f"{API}/getmatchdata/{COBERTURA[l['id']]}/{temporada}"):
            data = (m.get("matchDateTimeUTC") or "").replace("Z", "")[:16] + "Z"
            if not (ini <= data[:10] <= fim):
                continue
            final = [r for r in m.get("matchResults") or [] if r.get("resultTypeID") == 2]
            r = final[0] if final else None
            if m.get("matchIsFinished"):
                estado = "encerrado"
            elif r or (m.get("goals") and not m.get("matchIsFinished")):
                estado = "ao_vivo"
            else:
                estado = "agendado"
            saida.append(jogo_simples(
                "openligadb", l["id"], m.get("matchID"), data,
                (m.get("team1") or {}).get("teamName"), (m.get("team2") or {}).get("teamName"),
                r and r.get("pointsTeam1"), r and r.get("pointsTeam2"), estado,
                escudo_casa=(m.get("team1") or {}).get("teamIconUrl"), escudo_fora=(m.get("team2") or {}).get("teamIconUrl"),
            ))
    return saida
