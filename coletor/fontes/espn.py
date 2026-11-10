"""ESPN: placar, estatísticas, escalações, lances e classificação (fonte mais completa)."""

from datetime import timedelta

from .base import FonteIndisponivel, agora, baixar, dia_de as dia, numero

NOME = "ESPN"
API = "https://site.api.espn.com/apis/site/v2/sports"
API_TABELA = "https://site.api.espn.com/apis/v2/sports"

TIPOS_LANCE = {
    "Goal": "Gol",
    "Goal - Header": "Gol de cabeça",
    "Goal - Free-kick": "Gol de falta",
    "Penalty - Scored": "Gol de pênalti",
    "Penalty - Missed": "Pênalti perdido",
    "Penalty - Saved": "Pênalti defendido",
    "Own Goal": "Gol contra",
    "Yellow Card": "Cartão amarelo",
    "Red Card": "Cartão vermelho",
    "Substitution": "Substituição",
    "Kickoff": "Início",
    "Halftime": "Intervalo",
    "Start 2nd Half": "Início do 2º tempo",
    "End Regular Time": "Fim do tempo normal",
    "Full Time": "Fim de jogo",
    "VAR": "VAR",
    "Start Delay": "Jogo paralisado",
    "End Delay": "Jogo retomado",
    "End Half": "Fim do 1º tempo",
    "Extra Time Start": "Início da prorrogação",
    "Penalty Shootout": "Disputa de pênaltis",
}

ESTATISTICAS_PT = {
    "possessionPct": "Posse de bola (%)",
    "totalShots": "Finalizações",
    "shotsOnTarget": "Finalizações no gol",
    "blockedShots": "Finalizações bloqueadas",
    "wonCorners": "Escanteios",
    "foulsCommitted": "Faltas",
    "offsides": "Impedimentos",
    "yellowCards": "Cartões amarelos",
    "redCards": "Cartões vermelhos",
    "saves": "Defesas",
    "totalPasses": "Passes",
    "accuratePasses": "Passes certos",
    "passPct": "Precisão de passe",
    "totalCrosses": "Cruzamentos",
    "accurateCrosses": "Cruzamentos certos",
    "totalLongBalls": "Lançamentos",
    "accurateLongBalls": "Lançamentos certos",
    "totalTackles": "Desarmes",
    "effectiveTackles": "Desarmes certos",
    "interceptions": "Interceptações",
    "totalClearance": "Cortes",
    "penaltyKickGoals": "Gols de pênalti",
    "penaltyKickShots": "Pênaltis cobrados",
    "shotPct": "Aproveitamento das finalizações",
    "crossPct": "Precisão de cruzamento",
    "longballPct": "Precisão de lançamento",
    "tacklePct": "Precisão de desarme",
    "effectiveClearance": "Cortes certos",
}

ESTADOS = {"pre": "agendado", "in": "ao_vivo", "post": "encerrado"}


def time_(t):
    t = t or {}
    cor = t.get("color")
    return {
        "id": t.get("id"),
        "nome": t.get("displayName") or t.get("name"),
        "curto": t.get("shortDisplayName") or t.get("abbreviation"),
        "sigla": t.get("abbreviation"),
        "escudo": t.get("logo") or ((t.get("logos") or [{}])[0].get("href")),
        "cor": f"#{cor}" if cor else None,
    }


def jogo(e, liga):
    c = (e.get("competitions") or [{}])[0]
    lados = {}
    for comp in c.get("competitors") or []:
        lados[comp.get("homeAway")] = {
            "time": time_(comp.get("team")),
            "placar": numero(comp.get("score")),
            "vencedor": comp.get("winner"),
            "campanha": ((comp.get("records") or [{}])[0]).get("summary"),
            "forma": comp.get("form"),
        }
    st = c.get("status") or e.get("status") or {}
    tipo = st.get("type") or {}
    venue = c.get("venue") or {}
    endereco = venue.get("address") or {}
    lances = []
    for d in c.get("details") or []:
        texto = (d.get("type") or {}).get("text")
        lances.append({
            "tipo": TIPOS_LANCE.get(texto, texto),
            "minuto": (d.get("clock") or {}).get("displayValue"),
            "time": (d.get("team") or {}).get("id"),
            "jogadores": [a.get("displayName") for a in d.get("athletesInvolved") or [] if a.get("displayName")],
            "gol": bool(d.get("scoringPlay")),
        })
    return {
        "id": e.get("id"),
        "liga": liga,
        "data": e.get("date") or c.get("date"),
        "dia": dia(e.get("date") or c.get("date")),
        "temporada": (e.get("season") or {}).get("year"),
        "rodada": ((c.get("notes") or [{}])[0]).get("headline"),
        "estado": "adiado" if any(x in (tipo.get("name") or "") for x in ("POSTPONED", "CANCELED", "SUSPENDED", "ABANDONED"))
        else ESTADOS.get(tipo.get("state"), tipo.get("state")),
        "situacao": tipo.get("shortDetail") or tipo.get("detail"),
        "relogio": st.get("displayClock"),
        "casa": lados.get("home"),
        "fora": lados.get("away"),
        "estadio": venue.get("fullName"),
        "cidade": endereco.get("city"),
        "publico": numero(c.get("attendance")) or None,
        "transmissao": [n for b in c.get("broadcasts") or [] for n in b.get("names") or []],
        "lances": lances,
    }


def detalhe(s, base):
    """Estatísticas, escalações e lances completos de um jogo."""
    id_casa = ((base.get("casa") or {}).get("time") or {}).get("id")

    # Estatísticas por time, pareadas lado a lado (casa x fora)
    por_time = {}
    for t in (s.get("boxscore") or {}).get("teams") or []:
        tid = (t.get("team") or {}).get("id")
        lado = "casa" if tid == id_casa else "fora"
        for st in t.get("statistics") or []:
            chave = st.get("name") or st.get("label")
            if not chave:
                continue
            item = por_time.setdefault(chave, {
                "chave": chave,
                "nome": ESTATISTICAS_PT.get(chave) or st.get("label") or chave,
                "casa": None,
                "fora": None,
            })
            item[lado] = st.get("displayValue")
    estatisticas = list(por_time.values())

    escalacoes = {}
    for r in s.get("rosters") or []:
        tid = (r.get("team") or {}).get("id")
        lado = r.get("homeAway") or ("casa" if tid == id_casa else "fora")
        lado = {"home": "casa", "away": "fora"}.get(lado, lado)
        escalacoes[lado] = {
            "formacao": r.get("formation"),
            "jogadores": [
                {
                    "nome": (p.get("athlete") or {}).get("displayName"),
                    "numero": p.get("jersey"),
                    "posicao": (p.get("position") or {}).get("abbreviation"),
                    "titular": bool(p.get("starter")),
                    "entrou": bool(p.get("subbedIn")),
                    "saiu": bool(p.get("subbedOut")),
                    "stats": {
                        x.get("name"): x.get("displayValue")
                        for x in p.get("stats") or []
                        if x.get("name") and x.get("displayValue") not in (None, "0", "")
                    },
                }
                for p in r.get("roster") or []
            ],
        }

    lances = []
    for k in s.get("keyEvents") or []:
        texto = (k.get("type") or {}).get("text")
        if texto in ("Kickoff", "End Regular Time"):
            continue
        lances.append({
            "tipo": TIPOS_LANCE.get(texto, texto),
            "minuto": (k.get("clock") or {}).get("displayValue"),
            "time": (k.get("team") or {}).get("displayName"),
            "texto": k.get("text") or k.get("shortText"),
            "jogadores": [
                (p.get("athlete") or {}).get("displayName")
                for p in k.get("participants") or []
                if (p.get("athlete") or {}).get("displayName")
            ],
            "gol": bool(k.get("scoringPlay")),
        })

    info = s.get("gameInfo") or {}
    return {
        "estatisticas": estatisticas,
        "escalacoes": escalacoes,
        "lances": lances,
        "arbitros": [o.get("displayName") for o in info.get("officials") or [] if o.get("displayName")],
        "publico": numero(info.get("attendance")) or None,
        "final": base.get("estado") == "encerrado",
        "atualizado": agora().isoformat(timespec="seconds"),
    }


def tabela(j):
    grupos = j.get("children") or [j]
    saida = []
    for g in grupos:
        linhas = []
        for i, en in enumerate((g.get("standings") or {}).get("entries") or []):
            st = {x.get("name"): x.get("value") for x in en.get("stats") or [] if x.get("name")}
            nota = en.get("note") or {}
            linhas.append({
                "pos": numero(st.get("rank")) or i + 1,
                "time": time_(en.get("team")),
                "pontos": numero(st.get("points")),
                "jogos": numero(st.get("gamesPlayed")),
                "vitorias": numero(st.get("wins")),
                "empates": numero(st.get("ties")),
                "derrotas": numero(st.get("losses")),
                "gols_pro": numero(st.get("pointsFor")),
                "gols_contra": numero(st.get("pointsAgainst")),
                "saldo": numero(st.get("pointDifferential")),
                "aproveitamento": numero(st.get("winPercent")),
                "zona": nota.get("description"),
                "zona_cor": nota.get("color"),
            })
        linhas.sort(key=lambda x: x["pos"])
        if linhas:
            saida.append({"nome": g.get("name") or j.get("name"), "linhas": linhas})
    return saida


# ----------------------------------------------------------------- coleta


def meses(inicio, fim):
    m, saida = inicio.replace(day=1), []
    while m <= fim:
        saida.append(m.strftime("%Y%m"))
        m = (m + timedelta(days=32)).replace(day=1)
    return saida


def jogos(liga, inicio, fim):
    """Jogos completos da liga entre as datas (a ESPN aceita só mês inteiro: AAAAMM)."""
    url = f"{API}/{liga['esporte']}/{liga['codigo']}"
    lim_ini, lim_fim = inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")
    saida = {}
    for m in meses(inicio, fim):
        for e in baixar(f"{url}/scoreboard?dates={m}&limit=500").get("events") or []:
            g = jogo(e, liga["id"])
            if g["id"] and g["dia"] and lim_ini <= g["dia"] <= lim_fim:
                saida[g["id"]] = g
    return list(saida.values())


def classificacao(liga):
    return tabela(baixar(f"{API_TABELA}/{liga['esporte']}/{liga['codigo']}/standings"))


def detalhe_jogo(liga, g):
    s = baixar(f"{API}/{liga['esporte']}/{liga['codigo']}/summary?event={g['id']}")
    return detalhe(s, g)
