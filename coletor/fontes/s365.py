"""365Scores: placar ao vivo e estatísticas em português (inclui gols esperados, xG)."""

from datetime import datetime, timedelta

from .base import baixar, jogo_simples, para_iso

NOME = "365Scores"
API = "https://webws.365scores.com/web"
PARAMS = "appTypeId=5&langId=31&timezoneName=America/Sao_Paulo&userCountryId=21"

# liga -> (esporte 365: 1 futebol, 2 basquete, 4 hóquei, id da competição)
COBERTURA = {
    "brasileirao": (1, 113), "brasileirao-b": (1, 116), "copa-do-brasil": (1, 115),
    "libertadores": (1, 102), "champions-league": (1, 572), "premier-league": (1, 7),
    "la-liga": (1, 11), "serie-a-italia": (1, 17), "bundesliga": (1, 25), "ligue-1": (1, 35),
    "liga-portugal": (1, 73), "mls": (1, 104), "nba": (2, 103),
}

# statusGroup: 1/2 = agendado, 3 = ao vivo, 4 = encerrado (ou adiado, pelo texto)
_ADIADOS = ("Adiado", "Cancelado", "Interrompido", "Suspenso", "WO", "Abandonado")


def _estado(g):
    grupo, texto = g.get("statusGroup"), g.get("statusText") or ""
    if any(t in texto for t in _ADIADOS):
        return "adiado"
    if grupo == 3:
        return "ao_vivo"
    if grupo == 4:
        return "encerrado"
    return "agendado"


def jogos(ligas, hoje):
    por_comp = {COBERTURA[l["id"]][1]: l["id"] for l in ligas if l["id"] in COBERTURA}
    if not por_comp:
        return []
    ini = (hoje - timedelta(days=3)).strftime("%d/%m/%Y")
    fim = (hoje + timedelta(days=3)).strftime("%d/%m/%Y")
    comps = ",".join(str(c) for c in por_comp)
    dados = baixar(f"{API}/games/allscores/?{PARAMS}&competitions={comps}&startDate={ini}&endDate={fim}&showOdds=false")
    saida = []
    for g in dados.get("games") or []:
        liga = por_comp.get(g.get("competitionId"))
        if not liga:
            continue
        try:
            inicio = datetime.fromisoformat(g["startTime"])
        except (KeyError, ValueError):
            continue
        estado = _estado(g)
        c, f = g.get("homeCompetitor") or {}, g.get("awayCompetitor") or {}
        ok = estado in ("ao_vivo", "encerrado")
        saida.append(jogo_simples(
            "365scores", liga, g.get("id"), para_iso(inicio), c.get("name"), f.get("name"),
            c.get("score") if ok and (c.get("score") or 0) >= 0 else None,
            f.get("score") if ok and (f.get("score") or 0) >= 0 else None,
            estado, situacao=g.get("shortStatusText") or g.get("statusText"),
        ))
    return saida


def estatisticas(id_jogo, id_casa_365=None):
    """Estatísticas do jogo: [{nome, casa, fora}]. A ordem dos times segue o 365."""
    dados = baixar(f"{API}/game/stats/?{PARAMS}&games={id_jogo}")
    jogo = (dados.get("games") or [{}])[0]
    casa_id = (jogo.get("homeCompetitor") or {}).get("id")
    linhas = {}
    for s in dados.get("statistics") or []:
        nome = s.get("name")
        if not nome:
            continue
        lado = "casa" if s.get("competitorId") == casa_id else "fora"
        linhas.setdefault(nome, {"chave": "365:" + nome, "nome": nome, "casa": None, "fora": None})[lado] = s.get("value")
    return list(linhas.values())
