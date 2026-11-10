#!/usr/bin/env python3
"""
Coletor de estatísticas esportivas.

Junta jogos, placares, estatísticas, escalações, lances e classificações de
11 fontes (ESPN, 365Scores, LiveScore, ge, CBF, NHL, MLB, OpenLigaDB,
TheSportsDB, FixtureDownload e openfootball), confere o placar de cada jogo
entre elas, guarda tudo na pasta `dados/` (o seu histórico, que só cresce) e
monta um site na pasta `site/`, aberto no navegador ao final.

Não precisa instalar nada além do Python 3.8+. Para rodar, dê duplo clique
no arquivo "Iniciar" do seu sistema. Para parar, feche a janela.

Opções (para uso avançado):
  --uma-vez           coleta uma vez e sai (sem repetir e sem abrir o navegador)
  --site PASTA        onde gerar o site (padrão: ./site)
  --dias-detalhe N    dias para trás em que busca o detalhe dos jogos (padrão: config)
"""

import argparse
import json
import os
import shutil
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))

import fontes  # noqa: E402
from fontes import espn, s365  # noqa: E402
from fontes.base import ErroCertificado, agora, numero  # noqa: E402
from fontes.combinar import combinar, conferir_tabela  # noqa: E402

DADOS = PASTA / "dados"
MODELO_SITE = PASTA / "painel" / "index.html"
CONFIG = PASTA / "config.json"

LIGAS_PADRAO = [
    # id, nome, esporte, código ESPN
    ("brasileirao", "Brasileirão Série A", "soccer", "bra.1"),
    ("brasileirao-b", "Brasileirão Série B", "soccer", "bra.2"),
    ("copa-do-brasil", "Copa do Brasil", "soccer", "bra.copa_do_brazil"),
    ("libertadores", "Copa Libertadores", "soccer", "conmebol.libertadores"),
    ("sul-americana", "Copa Sul-Americana", "soccer", "conmebol.sudamericana"),
    ("champions-league", "Champions League", "soccer", "uefa.champions"),
    ("premier-league", "Premier League", "soccer", "eng.1"),
    ("la-liga", "La Liga", "soccer", "esp.1"),
    ("serie-a-italia", "Serie A (Itália)", "soccer", "ita.1"),
    ("bundesliga", "Bundesliga", "soccer", "ger.1"),
    ("ligue-1", "Ligue 1", "soccer", "fra.1"),
    ("liga-portugal", "Liga Portugal", "soccer", "por.1"),
    ("mls", "MLS", "soccer", "usa.1"),
    ("nba", "NBA", "basketball", "nba"),
    ("nfl", "NFL", "football", "nfl"),
    ("nhl", "NHL", "hockey", "nhl"),
    ("mlb", "MLB", "baseball", "mlb"),
]

CONFIG_PADRAO = {
    "intervalo_minutos": 5,
    "dias_para_tras": 7,
    "dias_para_frente": 14,
    "dias_historico_inicial": 120,
    "dias_detalhe": 7,
    "dias_no_site": 45,
    "abrir_navegador": True,
    "fontes_desligadas": [],
    "ligas": [
        {"id": i, "nome": n, "esporte": e, "codigo": c, "ativa": e == "soccer" or i == "nba"}
        for i, n, e, c in LIGAS_PADRAO
    ],
}

# De quanto em quanto tempo (minutos) cada fonte é consultada. As de placar ao
# vivo vão a cada ciclo; as de calendário e tabela mudam pouco e são poupadas.
INTERVALO_FONTE = {
    "365scores": 0, "livescore": 0, "nhl": 0, "mlb": 0,
    "ge": 15, "openligadb": 30, "cbf": 60, "fixturedownload": 60,
    "thesportsdb": 60, "openfootball": 360,
}
MAX_DETALHES = 150


# ---------------------------------------------------------------- arquivos

def ler_json(caminho, padrao=None):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def salvar_json(caminho, dados):
    # Grava num arquivo temporário e troca no fim: fechar a janela no meio
    # da gravação não corrompe o histórico.
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, caminho)


def carregar_config():
    cfg = ler_json(CONFIG)
    if not cfg:
        cfg = json.loads(json.dumps(CONFIG_PADRAO))
        salvar_config(cfg)
        return cfg
    for k, v in CONFIG_PADRAO.items():
        cfg.setdefault(k, v)
    return cfg


def salvar_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ coleta

def _com_cache(nome, intervalo, funcao):
    """Executa a consulta à fonte ou reaproveita o último resultado se ainda está fresco."""
    arq = DADOS / "fontes" / f"{nome}.json"
    antigo = ler_json(arq)
    if antigo and intervalo:
        idade = (agora() - datetime.fromisoformat(antigo["quando"])).total_seconds() / 60
        if idade < intervalo:
            return antigo["dados"], antigo["quando"], True
    dados = funcao()
    quando = agora().isoformat(timespec="seconds")
    salvar_json(arq, {"quando": quando, "dados": dados})
    return dados, quando, False


def coletar(cfg, dias_detalhe):
    ligas = [l for l in cfg["ligas"] if l.get("ativa")]
    por_id = {l["id"]: l for l in ligas}
    hoje = agora()
    jogos = ler_json(DADOS / "jogos.json", {})
    inicio = hoje - timedelta(days=cfg["dias_para_tras"])
    if not jogos:
        inicio = hoje - timedelta(days=cfg["dias_historico_inicial"])
        print(f"  Primeira execução: montando histórico desde {inicio:%d/%m/%Y}…")
    fim = hoje + timedelta(days=cfg["dias_para_frente"])
    desligadas = set(cfg.get("fontes_desligadas") or [])
    estado_fontes = {}

    # 1) Todas as fontes ao mesmo tempo: ESPN (por liga) e as outras 10
    def tarefa_espn(l):
        return espn.jogos(l, inicio, fim), espn.classificacao(l)

    def tarefa_fonte(nome, modulo):
        return _com_cache(nome, INTERVALO_FONTE.get(nome, 0), lambda: modulo.jogos(ligas, hoje))

    def tarefa_tabela(nome, modulo, l):
        return _com_cache(f"{nome}-tabela-{l['id']}", 30, lambda: modulo.classificacao(l))

    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_espn = {l["id"]: ex.submit(tarefa_espn, l) for l in ligas} if "espn" not in desligadas else {}
        # Só consulta a fonte se ela cobre alguma liga ligada (ex.: NHL.com só com a NHL ativa)
        fut_fontes = {
            n: ex.submit(tarefa_fonte, n, m) for n, m in fontes.SECUNDARIAS.items()
            if n not in desligadas and n != "cbf" and any(l["id"] in m.COBERTURA for l in ligas)  # a CBF só tem tabela
        }
        fut_tab = {
            (n, l["id"]): ex.submit(tarefa_tabela, n, m, l)
            for n, m in fontes.TABELAS.items() if n not in desligadas
            for l in ligas if l["id"] in m.COBERTURA
        }

    espn_jogos, tabelas, ok_espn, erros_espn = {}, {}, 0, []
    for lid, fut in fut_espn.items():
        try:
            lista, tab = fut.result()
            espn_jogos[lid] = lista
            if tab:
                tabelas[lid] = {"espn": tab}
            ok_espn += 1
        except ErroCertificado:
            raise
        except Exception as e:  # uma liga com problema não derruba as outras
            erros_espn.append(f"{por_id[lid]['nome']}: {e}")
    if fut_espn:
        estado_fontes["espn"] = {
            "ok": ok_espn > 0, "jogos": sum(len(v) for v in espn_jogos.values()),
            "erro": "; ".join(erros_espn[:3]) or None, "quando": hoje.isoformat(timespec="seconds"),
        }

    secundarios = []
    for nome, fut in fut_fontes.items():
        try:
            lista, quando, _ = fut.result()
            lista = [s for s in lista if s.get("liga") in por_id]
            secundarios.extend(lista)
            estado_fontes[nome] = {"ok": True, "jogos": len(lista), "erro": None, "quando": quando}
        except ErroCertificado:
            raise
        except Exception as e:
            estado_fontes[nome] = {"ok": False, "jogos": 0, "erro": str(e)[:160], "quando": None}

    for (nome, lid), fut in fut_tab.items():
        e = estado_fontes.setdefault(nome, {"ok": False, "jogos": 0, "tabelas": 0, "erro": None, "quando": None})
        e.setdefault("tabelas", 0)
        try:
            tab, quando, _ = fut.result()
            if tab:
                tabelas.setdefault(lid, {})[nome] = tab
                e["tabelas"] += 1
                e["ok"], e["quando"] = True, e["quando"] or quando
        except ErroCertificado:
            raise
        except Exception as erro:  # tabela de reserva: se falhar, a principal continua
            e["erro"] = e["erro"] or str(erro)[:160]

    for nome in sorted(estado_fontes, key=lambda n: fontes.PRIORIDADE.index(n) if n in fontes.PRIORIDADE else 99):
        e = estado_fontes[nome]
        marca = "✔" if e["ok"] else "✖"
        qtd = f"{e['jogos']:4} jogos" + (f" + {e['tabelas']} tabelas" if e.get("tabelas") else "")
        print(f"  {marca} {fontes.NOMES.get(nome, nome):16} {qtd}" + (f"  ({e['erro']})" if e["erro"] else ""))

    # 2) Cruza os jogos das fontes, liga por liga
    for lid in por_id:
        secs = [s for s in secundarios if s["liga"] == lid and s.get("dia")]
        frescos = {g["id"]: g for g in espn_jogos.get(lid, [])}
        if not secs and not frescos:
            continue
        dias = [s["dia"] for s in secs] + [g["dia"] for g in frescos.values() if g.get("dia")]
        ini, fi = min(dias), max(dias)
        base = {
            gid: g for gid, g in jogos.items()
            if g["liga"] == lid and ":" not in gid and g.get("dia") and ini <= g["dia"] <= fi
        }
        base.update(frescos)
        # Jogos que só outras fontes tinham são refeitos a cada ciclo (podem ter aparecido na ESPN agora)
        for gid in [gid for gid, g in jogos.items() if ":" in gid and g["liga"] == lid and ini <= (g.get("dia") or "") <= fi]:
            del jogos[gid]
        for g in combinar(list(base.values()), secs, fontes.PRIORIDADE, fontes.SO_CONFIRMAM, fontes.TOLERANCIA_DIAS):
            jogos[g["id"]] = g
    salvar_json(DADOS / "jogos.json", jogos)

    # 3) Tabelas: ESPN, ou ge, ou CBF; conferidas umas com as outras
    for lid, porfonte in tabelas.items():
        for nome in ("espn", "ge", "cbf"):
            if porfonte.get(nome):
                principal = porfonte[nome]
                outras = {n: t for n, t in porfonte.items() if n != nome and t}
                salvar_json(DADOS / "tabelas" / f"{lid}.json", {
                    "fonte": nome, "grupos": principal, "conferencia": conferir_tabela(principal, outras),
                })
                break

    # 4) Detalhe dos jogos: ESPN (escalações, lances, estatísticas) e 365Scores (estatísticas, xG)
    corte = (hoje - timedelta(days=dias_detalhe)).strftime("%Y-%m-%d")
    pendentes = []
    for g in jogos.values():
        if g["liga"] not in por_id or not g.get("dia"):
            continue
        if g["estado"] == "ao_vivo" or (g["estado"] == "encerrado" and g["dia"] >= corte):
            antigo = ler_json(DADOS / "detalhes" / f"{g['id']}.json") or {}
            if g["estado"] == "ao_vivo" or not antigo.get("final"):
                pendentes.append((g, antigo))
    pendentes.sort(key=lambda p: (p[0]["estado"] != "ao_vivo", p[0].get("data") or ""))
    pendentes = pendentes[:MAX_DETALHES]

    def um_detalhe(item):
        g, antigo = item
        det = dict(antigo)
        erros = 0
        if ":" not in g["id"] and "espn" not in desligadas:
            try:
                det.update(espn.detalhe_jogo(por_id[g["liga"]], g))
            except ErroCertificado:
                raise
            except Exception:
                erros += 1
        id365 = ((g.get("fontes") or {}).get("365scores") or {}).get("id")
        if id365 and "365scores" not in desligadas:
            try:
                det["estatisticas_365"] = s365.estatisticas(id365)
            except ErroCertificado:
                raise
            except Exception:
                erros += 1
        det["final"] = g["estado"] == "encerrado" and erros == 0
        det["atualizado"] = agora().isoformat(timespec="seconds")
        salvar_json(DADOS / "detalhes" / f"{g['id']}.json", det)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(um_detalhe, pendentes))
    if pendentes:
        print(f"  ✔ detalhes de {len(pendentes)} jogos atualizados")
    return jogos, estado_fontes


# --------------------------------------------------- estatísticas próprias

def resumo_times(jogos):
    """Médias e números de cada time, calculados a partir do seu histórico."""
    times = {}
    for g in jogos.values():
        if g["estado"] != "encerrado" or not g.get("casa") or not g.get("fora"):
            continue
        det = ler_json(DADOS / "detalhes" / f"{g['id']}.json") or {}
        stats = {e["chave"]: e for e in det.get("estatisticas") or []}
        for lado, outro in (("casa", "fora"), ("fora", "casa")):
            eu, ele = g[lado], g[outro]
            tid = (eu.get("time") or {}).get("id")
            if not tid or eu.get("placar") is None or ele.get("placar") is None:
                continue
            chave = f"{g['liga']}:{tid}"
            t = times.setdefault(chave, {
                "liga": g["liga"], "time": eu["time"], "jogos": 0, "vitorias": 0, "empates": 0,
                "derrotas": 0, "gols_pro": 0, "gols_contra": 0, "sem_sofrer": 0, "ultimos": [],
                "_somas": {}, "_contagem": {},
            })
            t["jogos"] += 1
            t["gols_pro"] += eu["placar"]
            t["gols_contra"] += ele["placar"]
            if ele["placar"] == 0:
                t["sem_sofrer"] += 1
            r = "V" if eu["placar"] > ele["placar"] else "D" if eu["placar"] < ele["placar"] else "E"
            t[{"V": "vitorias", "D": "derrotas", "E": "empates"}[r]] += 1
            t["ultimos"].append((g.get("data") or g.get("dia") or "", r))
            for k in ("possessionPct", "totalShots", "shotsOnTarget", "wonCorners", "foulsCommitted", "yellowCards"):
                v = numero((stats.get(k) or {}).get(lado))
                if v is not None:
                    t["_somas"][k] = t["_somas"].get(k, 0) + v
                    t["_contagem"][k] = t["_contagem"].get(k, 0) + 1
    saida = []
    for t in times.values():
        t["ultimos"] = [r for _, r in sorted(t["ultimos"])[-5:]]
        t["medias"] = {k: round(t["_somas"][k] / t["_contagem"][k], 1) for k in t["_somas"]}
        t["com_estatisticas"] = max(t["_contagem"].values(), default=0)
        t["media_gols_pro"] = round(t["gols_pro"] / t["jogos"], 2)
        t["media_gols_contra"] = round(t["gols_contra"] / t["jogos"], 2)
        del t["_somas"], t["_contagem"]
        saida.append(t)
    return saida


# ----------------------------------------------------------------- site

def gerar_site(cfg, jogos, estado_fontes, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MODELO_SITE, destino / "index.html")

    hoje = agora()
    ini = (hoje - timedelta(days=cfg["dias_no_site"])).strftime("%Y-%m-%d")
    fim = (hoje + timedelta(days=cfg["dias_para_frente"])).strftime("%Y-%m-%d")
    ativas = [l for l in cfg["ligas"] if l.get("ativa")]
    ids = {l["id"] for l in ativas}

    lista = []
    for g in sorted(jogos.values(), key=lambda g: g.get("data") or g.get("dia") or ""):
        if g["liga"] in ids and g.get("dia") and ini <= g["dia"] <= fim:
            det = ler_json(DADOS / "detalhes" / f"{g['id']}.json")
            lista.append({**g, "detalhe": det} if det else g)

    pacote = {
        "gerado_em": hoje.isoformat(timespec="seconds"),
        "intervalo_minutos": cfg["intervalo_minutos"],
        "ligas": [{"id": l["id"], "nome": l["nome"], "esporte": l["esporte"]} for l in ativas],
        "jogos": lista,
        "tabelas": {l["id"]: ler_json(DADOS / "tabelas" / f"{l['id']}.json") for l in ativas},
        "times": [t for t in resumo_times(jogos) if t["liga"] in ids],
        "total_historico": len(jogos),
        "fontes": [
            {"id": n, "nome": fontes.NOMES.get(n, n), **e}
            for n, e in sorted(estado_fontes.items(), key=lambda x: fontes.PRIORIDADE.index(x[0]) if x[0] in fontes.PRIORIDADE else 99)
        ],
        "nomes_fontes": fontes.NOMES,
    }
    # Um arquivo .js (e não .json) para o site funcionar aberto direto do
    # computador: navegadores bloqueiam a leitura de .json fora de um servidor.
    tmp = destino / "dados.js.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("window.DADOS = ")
        json.dump(pacote, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    os.replace(tmp, destino / "dados.js")
    return destino / "index.html"


# ----------------------------------------------------------------- início

def ciclo(cfg, dias_detalhe, destino):
    print(f"\n[{agora():%d/%m %H:%M}] Coletando…")
    jogos, estado_fontes = coletar(cfg, dias_detalhe)
    pagina = gerar_site(cfg, jogos, estado_fontes, destino)
    ao_vivo = sum(1 for g in jogos.values() if g["estado"] == "ao_vivo")
    funcionando = sum(1 for e in estado_fontes.values() if e["ok"])
    print(f"  Pronto: {funcionando} de {len(estado_fontes)} fontes funcionando, "
          f"{len(jogos)} jogos no histórico, {ao_vivo} ao vivo agora.")
    return pagina


def main():
    p = argparse.ArgumentParser(description="Coletor de estatísticas esportivas")
    p.add_argument("--uma-vez", action="store_true")
    p.add_argument("--site", default=str(PASTA / "site"))
    p.add_argument("--dias-detalhe", type=int)
    args = p.parse_args()

    # Consoles antigos do Windows não mostram ✔ e acentos: troca por "?" em vez de travar.
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    cfg = carregar_config()
    dias_detalhe = args.dias_detalhe if args.dias_detalhe is not None else cfg["dias_detalhe"]

    print("=" * 60)
    print("  COLETOR DE ESTATÍSTICAS  ·  11 fontes")
    print("  Para parar, feche esta janela.")
    print(f"  Ligas e opções: {CONFIG}")
    print("=" * 60)

    try:
        pagina = ciclo(cfg, dias_detalhe, args.site)
    except ErroCertificado:
        print("\nO Python não conseguiu verificar o certificado de segurança dos sites.")
        print("No Mac, abra a pasta Aplicativos > Python 3.x e dê duplo clique em")
        print("'Install Certificates.command'. Depois rode o coletor de novo.")
        return 1

    if args.uma_vez:
        return 0

    if cfg.get("abrir_navegador", True):
        print(f"\n  Abrindo o site: {pagina}")
        webbrowser.open(pagina.as_uri())

    while True:
        minutos = max(1, int(cfg["intervalo_minutos"]))
        print(f"  Próxima atualização em {minutos} min. (o site recarrega sozinho)")
        time.sleep(minutos * 60)
        try:
            cfg = carregar_config()
            ciclo(cfg, dias_detalhe, args.site)
        except Exception as e:  # sem internet, por exemplo: tenta de novo no próximo ciclo
            print(f"  Falha nesta atualização: {e}. Tento de novo no próximo ciclo.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nColetor encerrado.")
