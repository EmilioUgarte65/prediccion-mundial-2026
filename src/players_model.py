"""Modelo bottom-up COMPLETO: ataque y defensa de cada equipo desde TODAS las
métricas de jugador disponibles (FBref masivo 2026).

ATAQUE  = goles + asistencias + amenaza de tiro (tiros a puerta) por 90'.
DEFENSA = intercepciones + tackles ganados por 90' (solidez defensiva).
Ambos ponderados por minutos (pesan los que de verdad juegan) y normalizados
a multiplicador ~1.0. Guarda data_user/team_player_attack.csv.
"""
from __future__ import annotations

import csv
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
# Usamos el masivo (tiene tiros, intercepciones, tackles); fallback al simple
SRC = os.path.join(ROOT, "data_user", "fbref_masivo_2026.csv")
SRC2 = os.path.join(ROOT, "data_user", "fbref_players_2026.csv")
OUT = os.path.join(ROOT, "data_user", "team_player_attack.csv")

# Mapeo de nombres FBref/football-data -> nombres canónicos que usa el motor
# (de get_wc2026_fixtures). Corrige el bug donde 8 equipos no recibían la señal.
CANON = {
    "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Bosnia & Herz.": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo", "Cabo Verde": "Cape Verde",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Korea Republic": "South Korea", "IR Iran": "Iran", "Czechia": "Czech Republic",
}


def canon(name):
    return CANON.get(str(name).strip(), str(name).strip())


def _num(df, *cands):
    for c in cands:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index)


def _real_goals_by_team():
    """Goles REALES por selección en el Mundial 2026 (football-data.org)."""
    p = os.path.join(ROOT, "data_user", "scorers_real_2026.csv")
    if not os.path.exists(p):
        return {}
    d = pd.read_csv(p)
    d["team"] = d["team"].map(canon)
    return d.groupby("team")["goals"].sum().to_dict()


def main():
    df = pd.read_csv(SRC if os.path.exists(SRC) else SRC2)
    df["team"] = df["team"].map(canon)   # normalizar a nombres del motor
    mins = _num(df, "Playing Time_Min")
    gls = _num(df, "Performance_Gls")
    ast = _num(df, "Performance_Ast")
    sot = _num(df, "Standard_SoT")          # tiros a puerta (amenaza)
    sh = _num(df, "Standard_Sh")            # tiros totales
    intc = _num(df, "Performance_Int")      # intercepciones
    tkl = _num(df, "Performance_TklW")      # tackles ganados
    df = df.assign(_min=mins, _gls=gls, _ast=ast, _sot=sot, _sh=sh,
                   _int=intc, _tkl=tkl)
    team = "team"

    rows = []
    for t, g in df.groupby(team):
        tm = g["_min"].sum()
        if tm < 90:
            continue
        att = (g["_gls"].sum() + 0.4 * g["_ast"].sum()
               + 0.08 * g["_sot"].sum() + 0.02 * g["_sh"].sum()) / tm * 90
        dfn = (g["_int"].sum() + g["_tkl"].sum()) / tm * 90
        rows.append({"team": t, "att90": att, "def90": dfn})

    # Goles REALES del torneo (señal de "quién anota AHORA", sin fuga: ya jugados)
    real = _real_goals_by_team()
    ravg = (np.mean(list(real.values())) if real else 1.0) or 1.0

    aavg = np.mean([r["att90"] for r in rows]) or 1.0
    davg = np.mean([r["def90"] for r in rows]) or 1.0
    for r in rows:
        att_fbref = r["att90"] / aavg                      # potencial (FBref)
        rg = real.get(r["team"])
        att_real = (rg / ravg) if rg is not None else 1.0  # output real del torneo
        # 60% potencial + 40% realidad (si hay dato real del equipo)
        w_real = 0.4 if rg is not None else 0.0
        blended = (1 - w_real) * att_fbref + w_real * att_real
        r["real_goals"] = int(rg) if rg is not None else 0
        r["attack_mult"] = round(float(np.clip(blended, 0.85, 1.15)), 3)
        # más actividad defensiva -> reduce gol rival (efecto suave, acotado)
        r["def_mult"] = round(float(np.clip(r["def90"] / davg, 0.93, 1.07)), 3)
        r["att90"] = round(r["att90"], 2); r["def90"] = round(r["def90"], 2)
    rows.sort(key=lambda r: r["attack_mult"], reverse=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "att90", "def90", "real_goals",
                                          "attack_mult", "def_mult"])
        w.writeheader(); w.writerows(rows)
    print(f"OK -> {OUT}  ({len(rows)} equipos, ataque+defensa)")
    print("Top ataque:", [(r["team"], r["attack_mult"]) for r in rows[:4]])
    drows = sorted(rows, key=lambda r: r["def_mult"], reverse=True)
    print("Top defensa:", [(r["team"], r["def_mult"]) for r in drows[:4]])


if __name__ == "__main__":
    main()
