"""Prueba features NUEVAS para XGBoost (derivadas de las existentes), walk-forward
sin fuga: entrena con partidos < 2024, mide en >= 2024 (2616 partidos) y en WC.
Reporta el aporte de cada feature. Confirmar el ganador luego en el backtest.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from xgboost import XGBClassifier

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_prep import load_results
from ratings import compute_elo, GoalsModel
from model import FeatureBuilder, FEATURES

PARAMS = dict(n_estimators=400, max_depth=4, learning_rate=0.04, subsample=0.85,
              colsample_bytree=0.85, min_child_weight=3, reg_lambda=1.5,
              objective="multi:softprob", num_class=3, eval_metric="mlogloss", n_jobs=-1)


def main():
    print("Construyendo features...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    f = fb.build_training(results)
    f["date"] = results["date"].to_numpy()
    f["tournament"] = results["tournament"].to_numpy()

    # features DERIVADAS candidatas (de columnas ya existentes)
    f["rest_diff"] = f["home_rest"] - f["away_rest"]
    f["ppg_diff"] = f["home_ppg"] - f["away_ppg"]
    f["gf_diff"] = f["home_gf"] - f["away_gf"]
    f["ga_diff"] = f["away_ga"] - f["home_ga"]
    f["atk_vs_def_h"] = f["home_gf"] - f["away_ga"]
    f["atk_vs_def_a"] = f["away_gf"] - f["home_ga"]
    f["elo_x_neutral"] = f["elo_diff"] * f["neutral"]
    f["lam_ratio"] = f["lam_h"] / (f["lam_a"] + 0.1)
    f["elo_diff_sq"] = np.sign(f["elo_diff"]) * (f["elo_diff"] ** 2) / 1000

    cut = np.datetime64("2024-01-01")
    tr, va = f["date"] < cut, f["date"] >= cut
    wc = va & (f["tournament"] == "FIFA World Cup")
    ytr, yva, ywc = f.loc[tr, "label"], f.loc[va, "label"], f.loc[wc, "label"]

    def test(extra, name):
        cols = FEATURES + extra
        clf = XGBClassifier(**PARAMS)
        clf.fit(f.loc[tr, cols], ytr)
        acc = accuracy_score(yva, clf.predict_proba(f.loc[va, cols]).argmax(1)) * 100
        awc = accuracy_score(ywc, clf.predict_proba(f.loc[wc, cols]).argmax(1)) * 100
        return acc, awc

    base = test([], "base")
    print(f"\n{'Prueba':<34}{'Global':>8}{'WC':>7}{'ΔGlobal':>9}")
    print(f"{'BASE (features actuales)':<34}{base[0]:>7.1f}%{base[1]:>6.1f}%{'—':>9}")
    cand = ["rest_diff", "ppg_diff", "gf_diff", "ga_diff", "atk_vs_def_h",
            "atk_vs_def_a", "elo_x_neutral", "lam_ratio", "elo_diff_sq"]
    results_log = []
    for c in cand:
        a, w = test([c], c)
        d = a - base[0]
        results_log.append((c, d, a, w))
        print(f"{'+ ' + c:<34}{a:>7.1f}%{w:>6.1f}%{d:>+8.1f}")
    # todas las que ayudaron juntas
    helpers = [c for c, d, a, w in results_log if d > 0]
    if helpers:
        a, w = test(helpers, "helpers")
        print(f"\n{'+ TODAS las que ayudaron':<34}{a:>7.1f}%{w:>6.1f}%{a-base[0]:>+8.1f}")
        print("  helpers:", helpers)


if __name__ == "__main__":
    main()
