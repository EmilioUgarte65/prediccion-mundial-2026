"""¿Se puede acertar más el MARCADOR? Usa las lambdas ya calculadas (sin fuga)
de los partidos 2026 del backtest y prueba distintas reglas de marcador:
- rho de Dixon-Coles (varios valores)
- modal condicionado al resultado vs modal libre
Mide % de marcador EXACTO.
"""
from __future__ import annotations

import os
import json
import numpy as np
from scipy.stats import poisson

ROOT = os.path.dirname(os.path.dirname(__file__))


def modal(lh, la, rho, maxg=8, outcome=None):
    g = np.outer(poisson.pmf(np.arange(maxg + 1), lh), poisson.pmf(np.arange(maxg + 1), la))
    g[0, 0] *= 1 - lh * la * rho; g[0, 1] *= 1 + lh * rho
    g[1, 0] *= 1 + la * rho; g[1, 1] *= 1 - rho
    if outcome is not None:
        ii, jj = np.indices(g.shape)
        if outcome == 0:
            g = np.where(ii > jj, g, -1)
        elif outcome == 2:
            g = np.where(ii < jj, g, -1)
        else:
            g = np.where(ii == jj, g, -1)
    i, j = np.unravel_index(g.argmax(), g.shape)
    return int(i), int(j)


def main():
    bt = json.load(open(os.path.join(ROOT, "web", "data", "backtest.json"), encoding="utf-8"))
    ms = [m for m in bt["matches"] if "lh" in m and m.get("eligible")]
    print(f"Partidos 2026 con lambda: {len(ms)}\n")
    LBL = {"1": 0, "X": 1, "2": 2}

    def exact_rate(rho, conditioned):
        ex = mae = 0
        for m in ms:
            lh, la = m["lh"], m["la"]
            o = LBL[m["pred"]] if conditioned else None
            sh, sa = modal(lh, la, rho, outcome=o)
            rh, ra = m["real_score"]
            ex += int(sh == rh and sa == ra)
            mae += abs(sh - rh) + abs(sa - ra)
        return ex / len(ms) * 100, mae / (2 * len(ms))

    print(f"{'Regla':<34}{'Exacto':>8}{'MAE':>8}")
    for rho in (-0.20, -0.15, -0.12, -0.05, 0.0, 0.05, 0.10):
        e, m = exact_rate(rho, True)
        tag = "  <- actual" if abs(rho + 0.12) < 1e-9 else ""
        print(f"rho={rho:+.2f} condicionado{'':<10}{e:>7.1f}%{m:>8.3f}{tag}")
    print()
    for rho in (-0.12, -0.05, 0.0):
        e, m = exact_rate(rho, False)
        print(f"rho={rho:+.2f} modal LIBRE{'':<13}{e:>7.1f}%{m:>8.3f}")


if __name__ == "__main__":
    main()
