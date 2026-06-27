"""Validación de GOLEADORES: predicho (forma previa) vs real (torneo 2026).

Predicho = ranking por goles recientes 2024-26 (señal pre-torneo, sin fuga).
Real     = goleadores reales del Mundial (football-data.org).
Mide cuántos de los goleadores reales estaban en nuestro top previsto.
"""
from __future__ import annotations

import os
import unicodedata

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower().strip()


def main():
    traj = pd.read_csv(os.path.join(ROOT, "data_user", "player_trajectory.csv"))
    real = pd.read_csv(os.path.join(ROOT, "data_user", "scorers_real_2026.csv"))
    traj["k"] = traj["player"].map(norm)
    real["k"] = real["player"].map(norm)

    pred = traj.sort_values("goals_2024_26", ascending=False).reset_index(drop=True)
    pred_rank = {k: i for i, k in enumerate(pred["k"])}

    real_top = real.sort_values("goals", ascending=False).head(15)
    print("=== Goleadores REALES top-15 vs nuestro ranking previsto ===")
    hits_top30 = hits_top60 = 0
    for _, r in real_top.iterrows():
        pr = pred_rank.get(r["k"])
        pos = f"#{pr+1}" if pr is not None else "no listado"
        mark = ""
        if pr is not None and pr < 30:
            hits_top30 += 1; mark = " ✓top30"
        if pr is not None and pr < 60:
            hits_top60 += 1
        print(f"  {r['player']:<22} {int(r['goals'])} goles  | previsto: {pos}{mark}")

    n = len(real_top)
    print(f"\nDe los {n} máximos goleadores reales:")
    print(f"  en nuestro TOP-30 previsto: {hits_top30}/{n} ({hits_top30/n*100:.0f}%)")
    print(f"  en nuestro TOP-60 previsto: {hits_top60}/{n} ({hits_top60/n*100:.0f}%)")
    # ¿el máximo goleador real estaba en nuestro top-10?
    top_real = real_top.iloc[0]
    pr = pred_rank.get(top_real["k"])
    print(f"\nMáximo goleador real: {top_real['player']} "
          f"(previsto #{pr+1 if pr is not None else '—'})")


if __name__ == "__main__":
    main()
