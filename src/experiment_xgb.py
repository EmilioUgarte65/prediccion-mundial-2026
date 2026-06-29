"""Búsqueda de hiperparámetros para XGBoost (sin fuga): entrena con partidos
ANTERIORES a un corte y mide en los posteriores. Busca el mejor acierto posible.
"""
from __future__ import annotations

import os
import itertools
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from xgboost import XGBClassifier

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_prep import load_results
from ratings import compute_elo, GoalsModel
from model import FeatureBuilder, FEATURES


def main():
    print("Construyendo features (una vez)...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    feats["date"] = results["date"].to_numpy()
    feats["tournament"] = results["tournament"].to_numpy()

    cut = np.datetime64("2024-01-01")
    tr = feats["date"] < cut
    va = feats["date"] >= cut
    Xtr, ytr = feats.loc[tr, FEATURES], feats.loc[tr, "label"]
    Xva, yva = feats.loc[va, FEATURES], feats.loc[va, "label"]
    wc = va & (feats["tournament"] == "FIFA World Cup")
    Xwc, ywc = feats.loc[wc, FEATURES], feats.loc[wc, "label"]
    print(f"train={tr.sum()}  valid={va.sum()}  (de ellos WC={wc.sum()})\n")

    # config actual (baseline)
    base = dict(n_estimators=400, max_depth=4, learning_rate=0.04, subsample=0.85,
                colsample_bytree=0.85, min_child_weight=3, reg_lambda=1.5,
                objective="multi:softprob", num_class=3, eval_metric="mlogloss", n_jobs=-1)

    def score(params, label):
        clf = XGBClassifier(**params)
        clf.fit(Xtr, ytr)
        pv = clf.predict_proba(Xva)
        acc = accuracy_score(yva, pv.argmax(1)) * 100
        ll = log_loss(yva, pv, labels=[0, 1, 2])
        accwc = accuracy_score(ywc, clf.predict_proba(Xwc).argmax(1)) * 100
        print(f"  {label:<46}{acc:>6.1f}% | WC {accwc:>5.1f}% | ll {ll:.3f}")
        return acc, accwc

    print("ACTUAL:")
    best = (*score(base, "depth4 lr.04 n400 mcw3 lam1.5"), base)

    print("\nBúsqueda:")
    grid = {
        "max_depth": [3, 4, 5, 6],
        "learning_rate": [0.02, 0.05, 0.1],
        "n_estimators": [300, 600],
        "min_child_weight": [3, 6],
        "reg_lambda": [1.0, 3.0],
    }
    keys = list(grid)
    for combo in itertools.product(*[grid[k] for k in keys]):
        p = dict(base); p.update(dict(zip(keys, combo)))
        acc, accwc = score(p, " ".join(f"{k[:3]}{v}" for k, v in zip(keys, combo)))
        if acc > best[0]:
            best = (acc, accwc, p)

    print(f"\n=== MEJOR config: valid {best[0]:.1f}% | WC {best[1]:.1f}% ===")
    print("   ", {k: best[2][k] for k in keys})


if __name__ == "__main__":
    main()
