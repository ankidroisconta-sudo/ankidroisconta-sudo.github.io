#!/usr/bin/env python3
"""
Coletor de estatísticas esportivas.

Busca jogos, placares, estatísticas, escalações, lances e classificações nas
páginas de dados públicas da ESPN, guarda tudo na pasta `dados/` (o seu
histórico, que só cresce) e monta um site na pasta `site/`, aberto no
navegador ao final.

Não precisa instalar nada além do Python 3.8+. Para rodar, dê duplo clique
no arquivo "Iniciar" do seu sistema. Para parar, feche a janela.

Opções (para uso avançado):
  --uma-vez           coleta uma vez e sai (sem repetir e sem abrir o navegador)
  --site PASTA        onde gerar o site (padrão: ./site)
  --dias-detalhe N    dias para trás em que busca o detalhe dos jogos (padrão: config)
"""

import argparse
import gzip
import json
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
MODELO_SITE = PASTA / "painel" / "index.html"
CONFIG = PASTA / "config.json"

BRASILIA = timezone(timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019
API = "https://site.api.espn.com/apis/site/v2/sports"
API_TABELA = "https://site.api.espn.com/apis/v2/sports"
USER_AGENT = "coletor-estatisticas/1.0"

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
    "dias_historico_inicial": 120,
    "dias_para_frente": 14,
    "dias_detalhe": 7,
    "dias_no_site": 45,
    "abrir_navegador": True,
    "ligas": [
        {"id": i, "nome": n, "esporte": e, "codigo": c, "ativa": e == "soccer" or i == "nba"}
        for i, n, e, c in LIGAS_PADRAO
    ],
}

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


class ErroCertificado(Exception):
    pass


# ---------------------------------------------------------------- utilidades

def agora():
    return datetime.now(BRASILIA)


def dia(iso):
    """Data (AAAA-MM-DD, horário de Brasília) de um horário ISO da ESPN."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(BRASILIA).strftime("%Y-%m-%d")


def numero(v):
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return int(n) if n.is_integer() else n


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


def baixar(url, tentativas=3):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"},
    )
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                bruto = r.read()
            if bruto[:2] == b"\x1f\x8b":
                bruto = gzip.decompress(bruto)
            return json.loads(bruto.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                raise RuntimeError(f"HTTP {e.code}") from e
            ultimo = e
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                raise ErroCertificado() from e
            ultimo = e
        except (TimeoutError, json.JSONDecodeError, OSError) as e:
            ultimo = e
        time.sleep(2 ** i)
    raise RuntimeError(str(ultimo))


# ------------------------------------------------------------ normalização

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
        "estado": ESTADOS.get(tipo.get("state"), tipo.get("state")),
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

def carregar_config():
    cfg = ler_json(CONFIG)
    if not cfg:
        salvar_config(CONFIG_PADRAO)
        return json.loads(json.dumps(CONFIG_PADRAO))
    for k, v in CONFIG_PADRAO.items():
        cfg.setdefault(k, v)
    return cfg


def salvar_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def meses(inicio, fim):
    m, saida = inicio.replace(day=1), []
    while m <= fim:
        saida.append(m.strftime("%Y%m"))
        m = (m + timedelta(days=32)).replace(day=1)
    return saida


def coletar(cfg, dias_detalhe):
    ligas = [l for l in cfg["ligas"] if l.get("ativa")]
    hoje = agora()
    inicio = hoje - timedelta(days=cfg["dias_para_tras"])
    fim = hoje + timedelta(days=cfg["dias_para_frente"])
    lim_ini, lim_fim = inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")

    jogos = ler_json(DADOS / "jogos.json", {})
    if not jogos:
        # Primeira execução: busca alguns meses para trás e já começa com histórico
        # (placar e gols; as estatísticas completas vêm só dos últimos dias).
        inicio = hoje - timedelta(days=cfg["dias_historico_inicial"])
        lim_ini = inicio.strftime("%Y-%m-%d")
        print(f"  Primeira execução: montando histórico desde {inicio:%d/%m/%Y}…")
    problemas = []

    def uma_liga(l):
        url = f"{API}/{l['esporte']}/{l['codigo']}"
        novos = {}
        for m in meses(inicio, fim):
            j = baixar(f"{url}/scoreboard?dates={m}&limit=500")
            for e in j.get("events") or []:
                g = jogo(e, l["id"])
                if g["id"] and g["dia"] and lim_ini <= g["dia"] <= lim_fim:
                    novos[g["id"]] = g
        tab = tabela(baixar(f"{API_TABELA}/{l['esporte']}/{l['codigo']}/standings"))
        return novos, tab

    with ThreadPoolExecutor(max_workers=4) as ex:
        resultados = {l["id"]: ex.submit(uma_liga, l) for l in ligas}
    for l in ligas:
        try:
            novos, tab = resultados[l["id"]].result()
            jogos.update(novos)
            if tab:
                salvar_json(DADOS / "tabelas" / f"{l['id']}.json", tab)
            print(f"  ✔ {l['nome']}: {len(novos)} jogos")
        except ErroCertificado:
            raise
        except Exception as e:  # uma liga com problema não derruba as outras
            problemas.append(f"{l['nome']}: {e}")
            print(f"  ✖ {l['nome']}: {e}")
    salvar_json(DADOS / "jogos.json", jogos)

    # Detalhe: jogos ao vivo (sempre) e encerrados recentes ainda sem detalhe final
    corte = (hoje - timedelta(days=dias_detalhe)).strftime("%Y-%m-%d")
    por_id = {l["id"]: l for l in ligas}
    pendentes = []
    for g in jogos.values():
        if g["liga"] not in por_id:
            continue
        if g["estado"] == "ao_vivo":
            pendentes.append(g)
        elif g["estado"] == "encerrado" and g["dia"] >= corte:
            antigo = ler_json(DADOS / "detalhes" / f"{g['id']}.json")
            if not antigo or not antigo.get("final"):
                pendentes.append(g)
    pendentes.sort(key=lambda g: (g["estado"] != "ao_vivo", g["data"] or ""), reverse=False)
    pendentes = pendentes[:150]

    def um_detalhe(g):
        l = por_id[g["liga"]]
        s = baixar(f"{API}/{l['esporte']}/{l['codigo']}/summary?event={g['id']}")
        salvar_json(DADOS / "detalhes" / f"{g['id']}.json", detalhe(s, g))

    feitos = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for g, fut in [(g, ex.submit(um_detalhe, g)) for g in pendentes]:
            try:
                fut.result()
                feitos += 1
            except ErroCertificado:
                raise
            except Exception as e:
                problemas.append(f"detalhe do jogo {g['id']}: {e}")
    if pendentes:
        print(f"  ✔ detalhes de {feitos} jogos atualizados")
    return jogos, problemas


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
            tid = eu["time"]["id"]
            if not tid or eu["placar"] is None or ele["placar"] is None:
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
            t["ultimos"].append((g["data"] or "", r, g["id"]))
            for k in ("possessionPct", "totalShots", "shotsOnTarget", "wonCorners", "foulsCommitted", "yellowCards"):
                v = numero((stats.get(k) or {}).get(lado))
                if v is not None:
                    t["_somas"][k] = t["_somas"].get(k, 0) + v
                    t["_contagem"][k] = t["_contagem"].get(k, 0) + 1
    saida = []
    for t in times.values():
        t["ultimos"] = [r for _, r, _ in sorted(t["ultimos"])[-5:]]
        t["medias"] = {k: round(t["_somas"][k] / t["_contagem"][k], 1) for k in t["_somas"]}
        t["com_estatisticas"] = max(t["_contagem"].values(), default=0)
        t["media_gols_pro"] = round(t["gols_pro"] / t["jogos"], 2)
        t["media_gols_contra"] = round(t["gols_contra"] / t["jogos"], 2)
        del t["_somas"], t["_contagem"]
        saida.append(t)
    return saida


# ----------------------------------------------------------------- site

def gerar_site(cfg, jogos, problemas, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MODELO_SITE, destino / "index.html")

    hoje = agora()
    ini = (hoje - timedelta(days=cfg["dias_no_site"])).strftime("%Y-%m-%d")
    fim = (hoje + timedelta(days=cfg["dias_para_frente"])).strftime("%Y-%m-%d")
    ativas = [l for l in cfg["ligas"] if l.get("ativa")]
    ids = {l["id"] for l in ativas}

    lista = []
    for g in sorted(jogos.values(), key=lambda g: g["data"] or ""):
        if g["liga"] in ids and g["dia"] and ini <= g["dia"] <= fim:
            det = ler_json(DADOS / "detalhes" / f"{g['id']}.json")
            lista.append({**g, "detalhe": det} if det else g)

    pacote = {
        "gerado_em": hoje.isoformat(timespec="seconds"),
        "intervalo_minutos": cfg["intervalo_minutos"],
        "ligas": [{"id": l["id"], "nome": l["nome"], "esporte": l["esporte"]} for l in ativas],
        "jogos": lista,
        "tabelas": {l["id"]: ler_json(DADOS / "tabelas" / f"{l['id']}.json", []) for l in ativas},
        "times": [t for t in resumo_times(jogos) if t["liga"] in ids],
        "total_historico": len(jogos),
        "problemas": problemas,
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
    jogos, problemas = coletar(cfg, dias_detalhe)
    pagina = gerar_site(cfg, jogos, problemas, destino)
    ao_vivo = sum(1 for g in jogos.values() if g["estado"] == "ao_vivo")
    print(f"  Pronto: {len(jogos)} jogos no histórico, {ao_vivo} ao vivo agora.")
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

    print("=" * 56)
    print("  COLETOR DE ESTATÍSTICAS")
    print("  Para parar, feche esta janela.")
    print(f"  Ligas e opções: {CONFIG}")
    print("=" * 56)

    try:
        pagina = ciclo(cfg, dias_detalhe, args.site)
    except ErroCertificado:
        print("\nO Python não conseguiu verificar o certificado de segurança do site.")
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
