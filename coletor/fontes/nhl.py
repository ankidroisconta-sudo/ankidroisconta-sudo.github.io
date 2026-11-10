"""NHL (fonte oficial da liga)."""

from datetime import timedelta

from .base import baixar, jogo_simples

NOME = "NHL.com"
API = "https://api-web.nhle.com/v1/score"
COBERTURA = {"nhl": True}
_ESTADOS = {"FUT": "agendado", "PRE": "agendado", "LIVE": "ao_vivo", "CRIT": "ao_vivo", "FINAL": "encerrado", "OFF": "encerrado"}


def _nome(t):
    return " ".join(x for x in ((t.get("placeName") or {}).get("default"), (t.get("name") or {}).get("default")) if x)


def jogos(ligas, hoje):
    if not any(l["id"] == "nhl" for l in ligas):
        return []
    saida = []
    for d in (-1, 0, 1):
        dia = (hoje + timedelta(days=d)).strftime("%Y-%m-%d")
        for g in baixar(f"{API}/{dia}").get("games") or []:
            c, f = g.get("homeTeam") or {}, g.get("awayTeam") or {}
            estado = _ESTADOS.get(g.get("gameState"), "agendado")
            saida.append(jogo_simples(
                "nhl", "nhl", g.get("id"), (g.get("startTimeUTC") or "")[:16] + "Z", _nome(c), _nome(f),
                c.get("score"), f.get("score"), estado, escudo_casa=c.get("logo"), escudo_fora=f.get("logo"),
            ))
    return saida
