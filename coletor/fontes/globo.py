"""ge (Globo Esporte): classificação e jogos da rodada atual, lidos da página do campeonato."""

import json
import re

from .base import FonteIndisponivel, baixar, jogo_simples, para_iso
from datetime import datetime, timedelta, timezone

NOME = "ge"
SITE = "https://ge.globo.com/futebol"
COBERTURA = {
    "brasileirao": "brasileirao-serie-a",
    "brasileirao-b": "brasileirao-serie-b",
}
_BRT = timezone(timedelta(hours=-3))


def _dados(liga):
    html = baixar(f"{SITE}/{COBERTURA[liga]}/", texto=True)
    m = re.search(r"const\s+classificacao\s*=\s*", html)
    if not m:
        raise FonteIndisponivel("formato da página mudou")
    obj, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return obj


def jogos(ligas, hoje):
    saida = []
    for l in ligas:
        if l["id"] not in COBERTURA:
            continue
        for j in _dados(l["id"]).get("lista_jogos") or []:
            eq = j.get("equipes") or {}
            c, f = eq.get("mandante") or {}, eq.get("visitante") or {}
            try:
                inicio = datetime.strptime(j["data_realizacao"][:16], "%Y-%m-%dT%H:%M").replace(tzinfo=_BRT)
            except (KeyError, TypeError, ValueError):
                continue
            pc, pf = j.get("placar_oficial_mandante"), j.get("placar_oficial_visitante")
            if pc is not None and pf is not None:
                # A página não diz se acabou: com placar e mais de 2h15 do início, considera encerrado.
                estado = "encerrado" if inicio < datetime.now(_BRT) - timedelta(hours=2, minutes=15) else "ao_vivo"
            else:
                estado = "ao_vivo" if j.get("jogo_ja_comecou") else "agendado"
            saida.append(jogo_simples(
                "ge", l["id"], j.get("id"), para_iso(inicio), c.get("nome_popular"), f.get("nome_popular"),
                pc, pf, estado, escudo_casa=c.get("escudo"), escudo_fora=f.get("escudo"),
            ))
    return saida


def classificacao(liga):
    linhas = []
    for r in _dados(liga["id"]).get("classificacao") or []:
        linhas.append({
            "pos": r.get("ordem"), "time": {"id": None, "nome": r.get("nome_popular"), "sigla": r.get("sigla"), "escudo": r.get("escudo")},
            "pontos": r.get("pontos"), "jogos": r.get("jogos"), "vitorias": r.get("vitorias"),
            "empates": r.get("empates"), "derrotas": r.get("derrotas"), "gols_pro": r.get("gols_pro"),
            "gols_contra": r.get("gols_contra"), "saldo": r.get("saldo_gols"),
            "aproveitamento": (r.get("aproveitamento") or 0) / 100, "zona": None,
            "zona_cor": r.get("faixa_classificacao_cor"),
        })
    return [{"nome": None, "linhas": linhas}] if linhas else []
