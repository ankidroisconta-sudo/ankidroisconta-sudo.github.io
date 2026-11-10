"""TheSportsDB: base de dados esportiva aberta (chave pública de teste "123")."""

from datetime import timedelta

import time

from .base import FonteIndisponivel, baixar, jogo_simples

NOME = "TheSportsDB"
API = "https://www.thesportsdb.com/api/v1/json/123"
COBERTURA = {
    "brasileirao": 4351, "premier-league": 4328, "la-liga": 4335, "serie-a-italia": 4332,
    "bundesliga": 4331, "ligue-1": 4334, "liga-portugal": 4344, "mls": 4346,
    "champions-league": 4480, "libertadores": 4501, "nba": 4387, "nhl": 4380, "mlb": 4424,
}


POR_VEZ = 5  # ligas por consulta; as outras ficam para as próximas (a chave gratuita é lenta)


def jogos(ligas, hoje):
    saida = []
    cobertas = sorted((l for l in ligas if l["id"] in COBERTURA), key=lambda l: l["id"])
    if not cobertas:
        return saida
    # Revezamento: a cada hora, um grupo diferente de ligas
    grupos = [cobertas[i:i + POR_VEZ] for i in range(0, len(cobertas), POR_VEZ)]
    for l in grupos[hoje.hour % len(grupos)]:
        for d in (-1,):  # resultados de ontem: serve para confirmar o placar das outras fontes
            dia = (hoje + timedelta(days=d)).strftime("%Y-%m-%d")
            # A chave gratuita aceita cerca de 30 consultas por minuto: vai devagar
            # e, se o limite estourar, fica com o que já conseguiu.
            time.sleep(2.1)
            try:
                eventos = baixar(f"{API}/eventsday.php?d={dia}&l={COBERTURA[l['id']]}", tentativas=1).get("events") or []
            except FonteIndisponivel:
                if saida:
                    return saida
                raise
            for e in eventos:
                ts = (e.get("strTimestamp") or "")[:16]
                data = ts + "Z" if len(ts) == 16 else e.get("dateEvent")
                status = e.get("strStatus") or ""
                tem_placar = e.get("intHomeScore") not in (None, "")
                if status in ("Match Finished", "FT", "AET", "PEN", "AOT"):
                    estado = "encerrado"
                elif status in ("Postponed", "Cancelled", "PST", "CANC"):
                    estado = "adiado"
                elif tem_placar:
                    estado = "ao_vivo"
                else:
                    estado = "agendado"
                saida.append(jogo_simples(
                    "thesportsdb", l["id"], e.get("idEvent"), data, e.get("strHomeTeam"), e.get("strAwayTeam"),
                    e.get("intHomeScore"), e.get("intAwayScore"), estado,
                ))
    return saida
