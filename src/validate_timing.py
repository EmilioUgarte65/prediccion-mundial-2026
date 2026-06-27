"""Validación de los MINUTOS DE GOL (pedido original).

Walk-forward: ajusta la distribución de minutos solo con goles ANTERIORES a 2026
y compara su predicción por tramos de 15' contra los goles REALES de Mundiales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_prep import load_goalscorers, load_results
from goal_timing import GoalTimingModel, BUCKETS, BUCKET_LABELS


def bucketize(mins: pd.Series) -> np.ndarray:
    out = np.array([((mins >= lo) & (mins <= hi)).sum() for lo, hi in BUCKETS], float)
    return out / out.sum() if out.sum() else out


def main():
    g = load_goalscorers().copy()
    r = load_results().copy()
    g["date"] = pd.to_datetime(g["date"]); r["date"] = pd.to_datetime(r["date"])
    wc = r[r["tournament"] == "FIFA World Cup"][["date", "home_team", "away_team"]]
    gw = g.merge(wc, on=["date", "home_team", "away_team"], how="inner")
    gw = gw[(gw["minute"] >= 1) & (gw["minute"] <= 90)]

    cut = pd.Timestamp("2026-01-01")
    # Modelo entrenado SOLO con goles previos a 2026 (sin fuga)
    gt = GoalTimingModel().fit(g[g["date"] < cut])
    pred = np.array([gt.bucket_distribution()[l] for l in BUCKET_LABELS])

    real_all = bucketize(gw["minute"])                       # todos los Mundiales
    real_26 = bucketize(gw[gw["date"] >= cut]["minute"])     # solo 2026
    n26 = int((gw["date"] >= cut).sum())
    nall = int(len(gw))

    print(f"Goles de Mundial analizados: {nall} (histórico) | {n26} (2026)\n")
    print(f"{'Tramo':>7}{'Predicho':>11}{'Real WC':>11}{'Real 2026':>12}{'|err|':>9}")
    err = 0.0
    for i, lbl in enumerate(BUCKET_LABELS):
        e = abs(pred[i] - real_all[i]); err += e
        print(f"{lbl:>7}{pred[i]*100:>10.1f}%{real_all[i]*100:>10.1f}%"
              f"{real_26[i]*100:>11.1f}%{e*100:>8.1f}%")
    mae = err / len(BUCKET_LABELS)
    print(f"\nError medio por tramo (predicho vs WC histórico): {mae*100:.2f} pts")
    # 2da mitad mete más goles que 1ra (validación cualitativa)
    p1 = pred[:3].sum(); p2 = pred[3:].sum()
    r1 = real_all[:3].sum(); r2 = real_all[3:].sum()
    print(f"1er tiempo vs 2do — predicho {p1*100:.0f}/{p2*100:.0f} | real {r1*100:.0f}/{r2*100:.0f}")
    print("OK: el modelo captura que se anota más en la 2da mitad."
          if (p2 > p1) == (r2 > r1) else "REVISAR: tendencia invertida.")

    import json, os
    out = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "web", "data", "timing_validation.json")
    json.dump({
        "labels": BUCKET_LABELS,
        "pred": [round(float(x), 4) for x in pred],
        "real_all": [round(float(x), 4) for x in real_all],
        "real_2026": [round(float(x), 4) for x in real_26],
        "n_all": nall, "n_2026": n26, "mae_pts": round(float(mae * 100), 2),
    }, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"-> {out}")


if __name__ == "__main__":
    main()
