"""Modelo SOLO-2026: pesos por jugador (de sus partidos jugados) -> rating de
equipo desde el XI esperado (último que jugó), reactivo a lesiones.

ATAQUE  = por jugador: (goles + 0.7·asist + 0.2·tiros_a_puerta + 0.05·tiros)/partidos.
          El ataque del equipo = suma de su XI esperado disponible.
DEFENSA = a nivel equipo: goles recibidos por partido en 2026 (ESPN no da
          tackles/intercepciones por jugador).

Guarda data_user/team_ratings_2026.csv (team, attack, defense, n).
Sin datos históricos: todo de este Mundial.
"""
from __future__ import annotations

import csv
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, "data_user")
OUT = os.path.join(DATA, "team_ratings_2026.csv")


def _injured_set():
    p = os.path.join(DATA, "injuries_2026.csv")
    if not os.path.exists(p):
        return set()
    d = pd.read_csv(p)
    out = d[d["status"] == "out"]
    return set(zip(out["team"], out["player"]))


def main():
    pm = pd.read_csv(os.path.join(DATA, "player_match_stats_2026.csv"))
    for c in ["totalGoals", "goalAssists", "shotsOnTarget", "totalShots", "appearances"]:
        pm[c] = pd.to_numeric(pm[c], errors="coerce").fillna(0)

    # peso de ataque por jugador (contribución por partido jugado)
    pm["att_pts"] = (pm["totalGoals"] + 0.7 * pm["goalAssists"]
                     + 0.2 * pm["shotsOnTarget"] + 0.05 * pm["totalShots"])
    pw = pm.groupby(["team", "player"]).agg(
        att=("att_pts", "sum"), apps=("appearances", "sum")).reset_index()
    pw["att90"] = pw["att"] / pw["apps"].clip(lower=1)

    # XI esperado = jugadores que fueron TITULARES en el partido más reciente del equipo
    lu = pm.sort_values("date")
    last_game = lu.groupby("team")["gameId"].last()
    injured = _injured_set()

    # defensa: goles recibidos por partido (de results.csv, real)
    res = pd.read_csv(os.path.join(ROOT, "data_repo", "results.csv"))
    res = res[(res["tournament"] == "FIFA World Cup")
              & (res["date"] >= "2026-01-01")].copy()
    conceded = {}
    for r in res.itertuples():
        if pd.isna(r.home_score):
            continue
        conceded.setdefault(r.home_team, []).append(int(r.away_score))
        conceded.setdefault(r.away_team, []).append(int(r.home_score))

    rows = []
    for team in pw["team"].unique():
        gid = last_game.get(team)
        xi = pm[(pm["team"] == team) & (pm["gameId"] == gid) & (pm["starter"])]
        xi_players = set(xi["player"]) - {p for t, p in injured if t == team}
        tw = pw[(pw["team"] == team) & (pw["player"].isin(xi_players))]
        attack = float(tw["att90"].sum())
        # defensa con SHRINKAGE hacia la media (n=3-4 partidos -> un 0.0 es ruido)
        gc = conceded.get(team, [])
        PRIOR_N, PRIOR_GC = 4.0, 1.30
        defense = round((sum(gc) + PRIOR_N * PRIOR_GC) / (len(gc) + PRIOR_N), 2)
        rows.append({"team": team, "attack": round(attack, 3),
                     "defense": defense, "n_xi": len(xi_players)})

    # normalizar ataque a multiplicador y ACOTAR (evita λ extremas con muestra chica)
    avg_att = np.mean([r["attack"] for r in rows]) or 1.0
    for r in rows:
        r["attack_mult"] = round(float(np.clip(r["attack"] / avg_att, 0.7, 1.45)), 3)
    rows.sort(key=lambda r: r["attack"], reverse=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "attack", "attack_mult", "defense", "n_xi"])
        w.writeheader(); w.writerows(rows)
    print(f"OK -> {OUT} ({len(rows)} equipos)")
    print("Top ataque (XI 2026):", [(r["team"], r["attack_mult"]) for r in rows[:6]])
    best_def = sorted(rows, key=lambda r: r["defense"])[:5]
    print("Mejor defensa (menos GC/partido):", [(r["team"], r["defense"]) for r in best_def])


if __name__ == "__main__":
    main()
