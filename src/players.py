"""Módulo de jugadores: goleadores clave y dependencia de estrella por selección.

Usa goalscorers.csv (datos reales). Para cada equipo:
- top goleadores recientes (este Mundial + forma) con sus goles,
- 'dependencia de estrella' = % de los goles del equipo que aporta su máximo
  goleador (alta dependencia = más vulnerable si ese jugador no rinde/no juega).

Nota honesta: a nivel resultado esto YA está en el modelo de equipo; aquí es
información de jugador (quién es el peligro) + un dato de riesgo (dependencia).
"""
from __future__ import annotations

from collections import Counter, defaultdict

from data_prep import load_goalscorers

RECENT_FROM = "2023-06-01"   # ventana de "forma" reciente
WC_FROM = "2026-06-01"       # este Mundial


def team_scorers(min_date=RECENT_FROM, wc_from=WC_FROM):
    g = load_goalscorers()
    g = g[(g["own_goal"] != True)]  # noqa: E712
    rec = g[g["date"] >= min_date]
    wc = g[g["date"] >= wc_from]
    recent = defaultdict(Counter)   # team -> {player: goles recientes}
    wcgoals = defaultdict(Counter)  # team -> {player: goles en el Mundial}
    for r in rec.itertuples(index=False):
        recent[r.team][r.scorer] += 1
    for r in wc.itertuples(index=False):
        wcgoals[r.team][r.scorer] += 1

    out = {}
    for team, cnt in recent.items():
        total = sum(cnt.values())
        top = cnt.most_common(3)
        star_share = round(top[0][1] / total, 3) if total else 0.0
        out[team] = {
            "top": [{"name": n, "recent": c, "wc": int(wcgoals[team].get(n, 0))}
                    for n, c in top],
            "star_dependency": star_share,
            "recent_total": int(total),
        }
    return out


if __name__ == "__main__":
    ts = team_scorers()
    for t in ["Argentina", "France", "Norway", "Spain"]:
        d = ts.get(t)
        if d:
            stars = ", ".join(f"{p['name']} ({p['recent']})" for p in d["top"])
            print(f"{t}: {stars} | dependencia estrella {d['star_dependency']*100:.0f}%")
