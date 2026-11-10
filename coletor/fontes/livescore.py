"""LiveScore: placar ao vivo de futebol, basquete e hóquei."""

from datetime import datetime, timedelta, timezone

from .base import baixar, jogo_simples, para_iso

NOME = "LiveScore"
API = "https://prod-public-api.livescore.com/v1/api/app/date"

# liga -> (esporte no LiveScore, código do país/torneio, código exato da competição ou None = qualquer fase)
COBERTURA = {
    "brasileirao": ("soccer", "brazil", "serie-a"),
    "brasileirao-b": ("soccer", "brazil", "serie-b"),
    "copa-do-brasil": ("soccer", "brazil", "cup"),
    "libertadores": ("soccer", "copa-libertadores", None),
    "sul-americana": ("soccer", "copa-sudamericana", None),
    "champions-league": ("soccer", "champions-league", None),
    "premier-league": ("soccer", "england", "premier-league"),
    "la-liga": ("soccer", "spain", "laliga"),
    "serie-a-italia": ("soccer", "italy", "serie-a"),
    "bundesliga": ("soccer", "germany", "bundesliga"),
    "ligue-1": ("soccer", "france", "ligue-1"),
    "liga-portugal": ("soccer", "portugal", "primeira-liga"),
    "mls": ("soccer", "usa", "mls"),
    "nba": ("basketball", "nba", None),
    "nhl": ("hockey", "nhl", None),
}

_FIM = {"FT", "AET", "AP", "Ended", "AOT", "AOT.", "Fin"}
_ADIADO = {"Postp.", "Canc.", "Aband.", "Susp.", "Abd", "Postp", "Canc"}


def _estado(eps):
    eps = (eps or "").strip()
    if eps in _FIM:
        return "encerrado"
    if eps in _ADIADO:
        return "adiado"
    if eps in ("NS", "", "TBA"):
        return "agendado"
    return "ao_vivo"  # "67'", "HT", "Q3", "P2"...


def jogos(ligas, hoje):
    alvo = {l["id"]: COBERTURA[l["id"]] for l in ligas if l["id"] in COBERTURA}
    saida = []
    for esporte in sorted({c[0] for c in alvo.values()}):
        for d in (-1, 0, 1):
            dia = (hoje + timedelta(days=d)).strftime("%Y%m%d")
            # -3 = horário de Brasília nas datas devolvidas
            dados = baixar(f"{API}/{esporte}/{dia}/-3?MD=1")
            for st in dados.get("Stages") or []:
                for liga, (esp, pais, fase) in alvo.items():
                    if esp != esporte or st.get("Ccd") != pais:
                        continue
                    # Código exato: "premier-league-2" (sub-21) e "bundesliga-women" são outras ligas
                    if fase and st.get("Scd") != fase:
                        continue
                    for e in st.get("Events") or []:
                        esd = str(e.get("Esd") or "")
                        try:
                            inicio = datetime.strptime(esd[:12], "%Y%m%d%H%M").replace(tzinfo=timezone(timedelta(hours=-3)))
                        except ValueError:
                            continue
                        t1, t2 = (e.get("T1") or [{}])[0], (e.get("T2") or [{}])[0]
                        estado = _estado(e.get("Eps"))
                        saida.append(jogo_simples(
                            "livescore", liga, e.get("Eid"), para_iso(inicio),
                            t1.get("Nm"), t2.get("Nm"),
                            e.get("Tr1") if estado != "agendado" else None,
                            e.get("Tr2") if estado != "agendado" else None,
                            estado, situacao=e.get("Eps"),
                        ))
    return saida
