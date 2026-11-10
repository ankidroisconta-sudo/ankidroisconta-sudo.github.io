"""Cruza os jogos de várias fontes: acha o mesmo jogo em cada uma e decide o placar por maioria."""

from collections import Counter
from datetime import date

from .base import nome_chave, semelhanca

ORDEM_ESTADO = {"agendado": 0, "adiado": 1, "ao_vivo": 2, "encerrado": 3}


def _dias(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return 99


def _nome(lado):
    lado = lado or {}
    return (lado.get("time") or {}).get("nome") or lado.get("nome")


def _par(g, s, tolerancia=1):
    """Nota de 0 a 2 para "g e s são o mesmo jogo" (0 = não são)."""
    if g["liga"] != s["liga"] or _dias(g.get("dia"), s.get("dia")) > tolerancia:
        return 0
    a = semelhanca(_nome(g.get("casa")), s["casa"]["nome"])
    b = semelhanca(_nome(g.get("fora")), s["fora"]["nome"])
    # Um time joga uma vez por dia: um nome idêntico e outro parecido já basta.
    if a + b >= 1.5 and min(a, b) >= 0.5:
        return a + b
    if max(a, b) >= 0.95 and min(a, b) >= 0.35:
        return a + b
    return 0


def _resumo(s):
    return {"casa": s["casa"]["placar"], "fora": s["fora"]["placar"], "estado": s["estado"], "id": s["id"]}


def _novo(s):
    """Jogo que a ESPN não tem: entra com os dados da fonte que o achou."""
    return {
        "id": f"{s['fonte']}:{s['id']}",
        "liga": s["liga"],
        "data": s["data"] if s["data"] and len(s["data"]) > 10 else None,
        "dia": s["dia"],
        "estado": s["estado"],
        "situacao": s.get("situacao"),
        "relogio": s.get("situacao") if s["estado"] == "ao_vivo" else None,
        "casa": {"time": {"id": None, "nome": s["casa"]["nome"], "escudo": s["casa"].get("escudo")}, "placar": s["casa"]["placar"]},
        "fora": {"time": {"id": None, "nome": s["fora"]["nome"], "escudo": s["fora"].get("escudo")}, "placar": s["fora"]["placar"]},
        "lances": [],
        "fontes": {},
    }


def combinar(base, secundarios, prioridade, so_confirmam=(), tolerancia_dias=None):
    """
    base: jogos completos (da ESPN) de uma liga.
    secundarios: lista de jogos simples de todas as outras fontes.
    Devolve a lista final, cada jogo com `fontes`, `confirmacoes` e `divergentes`.
    """
    jogos = []
    for g in base:
        g = dict(g)
        g["fontes"] = {"espn": {"casa": (g.get("casa") or {}).get("placar"), "fora": (g.get("fora") or {}).get("placar"), "estado": g.get("estado"), "id": g["id"]}}
        jogos.append(g)

    # Fontes mais confiáveis primeiro: quem cria um jogo novo é a melhor fonte que o tem.
    ordem = {f: i for i, f in enumerate(prioridade)}
    vistos = set()
    for s in sorted(secundarios, key=lambda s: ordem.get(s["fonte"], 99)):
        if not s["casa"]["nome"] or not s["fora"]["nome"]:
            continue
        # A mesma fonte pode repetir um jogo (ex.: jogo da madrugada em dois dias)
        if (s["fonte"], s["id"]) in vistos:
            continue
        vistos.add((s["fonte"], s["id"]))
        tol = (tolerancia_dias or {}).get(s["fonte"], 1)
        melhor, nota = None, 0
        for g in jogos:
            if s["fonte"] in g["fontes"]:
                continue
            # Com data incerta, prefere o jogo de data mais próxima entre pares igualmente bons
            n = _par(g, s, tol)
            if n:
                n -= _dias(g.get("dia"), s.get("dia")) * 0.01
            if n > nota:
                melhor, nota = g, n
        if melhor is None:
            if s["fonte"] in so_confirmam:
                continue
            melhor = _novo(s)
            jogos.append(melhor)
        melhor["fontes"][s["fonte"]] = _resumo(s)
        if not (melhor.get("casa") or {}).get("time", {}).get("escudo") and s["casa"].get("escudo"):
            melhor["casa"]["time"]["escudo"] = s["casa"]["escudo"]
            melhor["fora"]["time"]["escudo"] = s["fora"].get("escudo")

    for g in jogos:
        _consenso(g, ordem)
    return jogos


def _consenso(g, ordem):
    fontes = g["fontes"]
    # O estado mais avançado vence (fontes atrasadas ainda mostram "agendado").
    estado = max((f["estado"] for f in fontes.values() if f.get("estado")), key=lambda e: ORDEM_ESTADO.get(e, 0), default=g.get("estado"))
    if estado == "adiado" and any(f.get("estado") == "encerrado" for f in fontes.values()):
        estado = "encerrado"
    com_placar = {
        nome: (f["casa"], f["fora"]) for nome, f in fontes.items()
        if f.get("estado") == estado and f.get("casa") is not None and f.get("fora") is not None
    }
    if com_placar and g.get("casa") and g.get("fora"):
        votos = Counter(com_placar.values())
        topo = max(votos.values())
        empatados = [p for p, v in votos.items() if v == topo]
        # Empate na votação: vale a fonte de maior prioridade
        placar = min(empatados, key=lambda p: min(ordem.get(n, 99) for n, x in com_placar.items() if x == p))
        g["casa"]["placar"], g["fora"]["placar"] = placar
        g["confirmacoes"] = sorted((n for n, x in com_placar.items() if x == placar), key=lambda n: ordem.get(n, 99))
        # Ao vivo, fontes atualizam em momentos diferentes: só aponta divergência em jogo encerrado.
        g["divergentes"] = sorted(n for n, x in com_placar.items() if x != placar) if estado == "encerrado" else []
    else:
        g["confirmacoes"], g["divergentes"] = [], []
    if estado != g.get("estado"):
        g["estado"] = estado
        if estado == "encerrado":
            g["situacao"] = "Fim"
    return g


def conferir_tabela(principal, outras):
    """Compara pontos de cada time da tabela principal com as outras fontes."""
    conferencia = []
    linhas = [l for grupo in principal for l in grupo["linhas"]]
    for fonte, tabela in outras.items():
        outras_linhas = [l for grupo in tabela for l in grupo["linhas"]]
        iguais = achados = 0
        for l in linhas:
            nome = (l.get("time") or {}).get("nome")
            cand = max(outras_linhas, key=lambda o: semelhanca(nome, (o.get("time") or {}).get("nome")), default=None)
            if cand and semelhanca(nome, cand["time"]["nome"]) >= 0.6:
                achados += 1
                if cand.get("pontos") == l.get("pontos") and cand.get("jogos") == l.get("jogos"):
                    iguais += 1
                for k in ("cartoes_amarelos", "cartoes_vermelhos"):
                    if cand.get(k) is not None:
                        l[k] = cand[k]
        conferencia.append({"fonte": fonte, "iguais": iguais, "comparados": achados, "total": len(linhas)})
    return conferencia


__all__ = ["combinar", "conferir_tabela", "nome_chave"]
