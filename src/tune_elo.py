"""Tunea los parámetros del Elo (factor K y ventaja de localía) sin fuga de futuro.

Optimiza el acierto del modelo-Elo en Mundiales 1998-2014 (dev) y lo mide en
2018-2026 (test). La curva de empate se ajusta SOLO con datos previos a 1998
(válido para dev y test). El Elo se recalcula walk-forward (cada rating es previo
al partido), así que ningún partido ve el futuro.
"""
import numpy as np
import pandas as pd

from data_prep import load_results
from ratings import compute_elo, HOME_ADV_ELO
from elomodel import EloModel


def wc_rows(results):
    wc = results[results["tournament"] == "FIFA World Cup"].copy()
    wc["year"] = wc["date"].dt.year
    return wc[wc["year"] >= 1998]


def acc(elom, sub):
    y = np.where(sub["home_score"] > sub["away_score"], 0,
                 np.where(sub["home_score"] < sub["away_score"], 2, 1))
    hit = 0
    for i, row in enumerate(sub.itertuples(index=False)):
        p = elom.outcome_probs(row.home_elo, row.away_elo, bool(row.neutral))
        if int(np.argmax(p)) == y[i]:
            hit += 1
    return hit / len(sub)


def evaluate(results, k_scale, hfa):
    r2, _ = compute_elo(results, k_scale=k_scale, hfa_val=hfa)
    pre = r2[r2["date"] < "1998-01-01"]
    lab = np.where(pre["home_score"] > pre["away_score"], 0,
                   np.where(pre["home_score"] < pre["away_score"], 2, 1))
    elom = EloModel().fit(pre["home_elo"].to_numpy(), pre["away_elo"].to_numpy(),
                          pre["neutral"].to_numpy(), lab)
    wc = wc_rows(r2)
    dev = wc[wc["year"] <= 2014]
    test = wc[wc["year"] >= 2018]
    return acc(elom, dev), acc(elom, test)


def main():
    results = load_results()
    print("Tuneando Elo (K y localía)... dev=1998-2014, test=2018-2026\n")
    base_dev, base_test = evaluate(results, 1.0, HOME_ADV_ELO)
    print(f"ACTUAL (K=x1.0, HFA={HOME_ADV_ELO:.0f}): dev {base_dev*100:.1f}% | test {base_test*100:.1f}%\n")

    best = (base_dev, 1.0, HOME_ADV_ELO, base_test)
    results_grid = []
    for ks in (0.6, 0.8, 1.0, 1.2, 1.5):
        for hfa in (40, 55, 70, 85, 100):
            d, t = evaluate(results, ks, hfa)
            results_grid.append((d, t, ks, hfa))
            if d > best[0]:
                best = (d, ks, hfa, t)
    print("Top 5 configs por acierto en DEV:")
    for d, t, ks, hfa in sorted(results_grid, reverse=True)[:5]:
        print(f"  K=x{ks}  HFA={hfa}:  dev {d*100:.1f}% | test {t*100:.1f}%")
    print(f"\nMEJOR (elegido por dev): K=x{best[1]} HFA={best[2]:.0f} "
          f"-> dev {best[0]*100:.1f}% | test {best[3]*100:.1f}%")
    print(f"vs ACTUAL test {base_test*100:.1f}%  -> "
          f"{'MEJORA' if best[3] > base_test else 'sin mejora'} "
          f"({(best[3]-base_test)*100:+.1f} pts)")


if __name__ == "__main__":
    main()
