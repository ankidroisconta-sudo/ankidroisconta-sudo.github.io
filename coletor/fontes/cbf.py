"""CBF (fonte oficial do futebol brasileiro): classificação com cartões."""

import html as _html
import re

from .base import FonteIndisponivel, agora, baixar

NOME = "CBF"
SITE = "https://www.cbf.com.br/futebol-brasileiro/tabelas/campeonato-brasileiro"
COBERTURA = {"brasileirao": "serie-a", "brasileirao-b": "serie-b"}


def jogos(ligas, hoje):
    return []  # a CBF entra só com a classificação


def classificacao(liga):
    pagina = baixar(f"{SITE}/{COBERTURA[liga['id']]}/{agora().year}", texto=True)
    i = pagina.find("<table")
    if i < 0:
        raise FonteIndisponivel("tabela não encontrada na página")
    tabela = pagina[i:pagina.find("</table>", i)]
    linhas = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tabela, re.S):
        nome = re.search(r'teamName[^"]*">([^<]+)<', tr)
        pos = re.search(r'position[^"]*">\s*(\d+)\s*<', tr)
        nums = [int(n) for n in re.findall(r">(-?\d+)</td>", tr)]
        if not nome or not pos or len(nums) < 11:
            continue
        pts, j, v, e, d, gp, gc, sg, ca, cv, apr = nums[:11]
        linhas.append({
            "pos": int(pos.group(1)), "time": {"id": None, "nome": _html.unescape(nome.group(1)).strip()},
            "pontos": pts, "jogos": j, "vitorias": v, "empates": e, "derrotas": d,
            "gols_pro": gp, "gols_contra": gc, "saldo": sg, "aproveitamento": apr / 100,
            "cartoes_amarelos": ca, "cartoes_vermelhos": cv, "zona": None, "zona_cor": None,
        })
    if not linhas:
        raise FonteIndisponivel("formato da tabela mudou")
    return [{"nome": None, "linhas": linhas}]
