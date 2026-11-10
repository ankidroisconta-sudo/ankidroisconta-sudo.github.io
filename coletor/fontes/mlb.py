"""MLB (fonte oficial da liga)."""

from datetime import timedelta

from .base import baixar, jogo_simples

NOME = "MLB.com"
API = "https://statsapi.mlb.com/api/v1/schedule"
COBERTURA = {"mlb": True}
_ESTADOS = {"Preview": "agendado", "Live": "ao_vivo", "Final": "encerrado"}


def jogos(ligas, hoje):
    if not any(l["id"] == "mlb" for l in ligas):
        return []
    ini, fim = (hoje - timedelta(days=1)).strftime("%Y-%m-%d"), (hoje + timedelta(days=1)).strftime("%Y-%m-%d")
    saida = []
    for d in baixar(f"{API}?sportId=1&startDate={ini}&endDate={fim}").get("dates") or []:
        for g in d.get("games") or []:
            c, f = (g.get("teams") or {}).get("home") or {}, (g.get("teams") or {}).get("away") or {}
            st = g.get("status") or {}
            estado = "adiado" if "Postponed" in (st.get("detailedState") or "") else _ESTADOS.get(st.get("abstractGameState"), "agendado")
            saida.append(jogo_simples(
                "mlb", "mlb", g.get("gamePk"), (g.get("gameDate") or "")[:16] + "Z",
                (c.get("team") or {}).get("name"), (f.get("team") or {}).get("name"),
                c.get("score"), f.get("score"), estado, situacao=st.get("detailedState"),
            ))
    return saida
