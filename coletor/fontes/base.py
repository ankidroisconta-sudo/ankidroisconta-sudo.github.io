"""Funções comuns a todas as fontes: download, datas e nomes de times."""

import gzip
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

BRASILIA = timezone(timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019
USER_AGENT = "coletor-estatisticas/2.0"


class ErroCertificado(Exception):
    pass


class FonteIndisponivel(Exception):
    """A fonte recusou ou não respondeu. As outras fontes seguem normalmente."""


def agora():
    return datetime.now(BRASILIA)


def baixar(url, tentativas=2, texto=False, timeout=20):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*" if texto else "application/json", "Accept-Encoding": "gzip"},
    )
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                bruto = r.read()
            if bruto[:2] == b"\x1f\x8b":
                bruto = gzip.decompress(bruto)
            corpo = bruto.decode("utf-8", errors="replace")
            return corpo if texto else json.loads(corpo)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410):
                raise FonteIndisponivel(f"HTTP {e.code}") from e
            ultimo = e
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                raise ErroCertificado() from e
            ultimo = e
        except (TimeoutError, json.JSONDecodeError, OSError) as e:
            ultimo = e
        time.sleep(1.5 * (i + 1))
    raise FonteIndisponivel(str(ultimo))


def numero(v):
    if v is None or v == "":
        return None
    try:
        n = float(str(v).replace("%", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return int(n) if n.is_integer() else n


def para_iso(dt):
    """datetime com fuso -> texto ISO em UTC (formato usado em todo o coletor)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def dia_de(iso):
    """Data AAAA-MM-DD no horário de Brasília."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRASILIA).strftime("%Y-%m-%d")


def jogo_simples(fonte, liga, id_, data_iso, casa, fora, placar_casa, placar_fora, estado,
                 situacao=None, escudo_casa=None, escudo_fora=None, extra=None):
    """Formato mínimo que toda fonte devolve. `estado`: agendado | ao_vivo | encerrado | adiado."""
    return {
        "fonte": fonte,
        "liga": liga,
        "id": str(id_),
        "data": data_iso,
        "dia": dia_de(data_iso),
        "casa": {"nome": casa, "placar": numero(placar_casa), "escudo": escudo_casa},
        "fora": {"nome": fora, "placar": numero(placar_fora), "escudo": escudo_fora},
        "estado": estado,
        "situacao": situacao,
        **(extra or {}),
    }


# ------------------------------------------------- comparação de nomes

_PALAVRAS_VAZIAS = {
    "fc", "cf", "sc", "ec", "ac", "afc", "cd", "ca", "se", "sa", "ssc", "as", "ss", "us", "rc", "rcd",
    "club", "clube", "de", "da", "do", "del", "la", "le", "el", "the", "futebol", "football", "calcio",
    "esporte", "sport", "sporting", "fk", "sv", "vfb", "vfl", "tsg", "bv", "1", "04", "05", "1899", "1846",
    "e", "y", "and",
}

# Nomes que nenhuma regra genérica aproxima. Chave e valor já normalizados.
_APELIDOS = {
    "man utd": "manchester united", "man united": "manchester united", "man city": "manchester city",
    "spurs": "tottenham hotspur", "tottenham": "tottenham hotspur", "wolves": "wolverhampton wanderers",
    "nottm forest": "nottingham forest", "newcastle": "newcastle united", "west ham": "west ham united",
    "brighton": "brighton hove albion", "leeds": "leeds united",
    "atletico mg": "atletico mineiro", "cam": "atletico mineiro", "galo": "atletico mineiro",
    "athletico": "athletico paranaense", "athletico pr": "athletico paranaense",
    "atletico pr": "athletico paranaense", "paranaense": "athletico paranaense",
    "bragantino": "red bull bragantino", "rb bragantino": "red bull bragantino",
    "vasco": "vasco gama", "ca mineiro": "atletico mineiro", "ca paranaense": "athletico paranaense",
    "psg": "paris saint germain", "paris sg": "paris saint germain",
    "bayern munchen": "bayern", "bayern munich": "bayern",
    "internazionale": "inter milan", "inter milano": "inter milan", "milan": "ac milan",
    "olympique lyonnais": "lyon", "olympique lyon": "lyon", "olympique marseille": "marseille",
    "olympique de marseille": "marseille", "stade brestois 29": "brest", "stade brestois": "brest",
    "losc lille": "lille", "losc": "lille", "rc strasbourg alsace": "strasbourg",
    "stade rennais": "rennes", "paris saint germain": "paris saint germain",
    "r racing club": "racing santander", "sporting kc": "sporting kansas city",
    "atletico madrid": "atletico madrid", "atl madrid": "atletico madrid", "atleti": "atletico madrid",
    "betis": "real betis", "sociedad": "real sociedad",
    "gladbach": "borussia monchengladbach", "m gladbach": "borussia monchengladbach",
    "dortmund": "borussia dortmund", "leverkusen": "bayer leverkusen",
    "la galaxy": "los angeles galaxy", "lafc": "los angeles", "inter miami": "inter miami",
}


def nome_chave(nome):
    """Nome do time sem acento, sem siglas genéricas e com apelidos resolvidos."""
    if not nome:
        return ""
    n = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = " ".join(n.split())
    if n in _APELIDOS:
        return _APELIDOS[n]
    tokens = [t for t in n.split() if t not in _PALAVRAS_VAZIAS]
    n = " ".join(tokens) or n
    return _APELIDOS.get(n, n)


def semelhanca(a, b):
    """0 a 1: quão provável é que dois nomes sejam o mesmo time."""
    a, b = nome_chave(a), nome_chave(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    # "Flamengo" x "Flamengo RJ", "Bahia" x "EC Bahia"
    if ta <= tb or tb <= ta:
        return 0.9
    jacc = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, a, b).ratio()  # grafias próximas: "Mönchengladbach" x "Monchengladbach"
    return max(jacc, seq)
