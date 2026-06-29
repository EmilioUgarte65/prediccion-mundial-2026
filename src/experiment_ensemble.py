"""¿Stacking mejora el Ensemble? Entrena el combinador en Mundiales <=2014 y
mide en 2018-2026 (sin fuga temporal). Compara: promedio simple, mejor lineal,
y stacking (regresión logística sobre las 9 probabilidades).
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss

ROOT_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_user")


def main():
    d = pd.read_csv(os.path.join(ROOT_DATA, "wc_backtest_probs.csv"))
    y = d["real"].map({"1": 0, "X": 1, "2": 2}).to_numpy()
    EL = d[["el1", "elx", "el2"]].to_numpy()
    S = d[["s1", "sx", "s2"]].to_numpy()
    P = d[["p1", "px", "p2"]].to_numpy()
    X = np.hstack([EL, S, P])
    dev = d["edition"].astype(int) <= 2014
    test = d["edition"].astype(int) >= 2018
    yd, yt = y[dev], y[test]

    def ev(prob, name):
        prob = prob / prob.sum(1, keepdims=True)
        acc = accuracy_score(yt, prob.argmax(1)) * 100
        ll = log_loss(yt, prob, labels=[0, 1, 2])
        print(f"  {name:<26}{acc:>7.1f}%   logloss {ll:.3f}")
        return acc

    print(f"Partidos: dev(<=2014)={dev.sum()}  test(2018-2026)={test.sum()}\n")
    print("Modelo combinado (medido en 2018-2026):")
    avg = (EL + S + P) / 3
    ev(avg[test], "Ensemble promedio")
    # mejor lineal (busca pesos en dev, mide en test)
    best = None
    for we in np.arange(0, 1.01, 0.1):
        for ws in np.arange(0, 1.01 - we, 0.1):
            wx = 1 - we - ws
            if wx < -1e-9:
                continue
            pr = we * EL[dev] + ws * S[dev] + wx * P[dev]
            ll = log_loss(yd, pr / pr.sum(1, keepdims=True), labels=[0, 1, 2])
            if best is None or ll < best[0]:
                best = (ll, we, ws, wx)
    _, we, ws, wx = best
    lin = we * EL + ws * S + wx * P
    ev(lin[test], f"Lineal tuneado {we:.1f}/{ws:.1f}/{wx:.1f}")
    # stacking logístico
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X[dev], yd)
    ev(clf.predict_proba(X[test]), "Stacking (logístico)")


if __name__ == "__main__":
    main()
