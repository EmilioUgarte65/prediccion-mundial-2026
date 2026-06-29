"""Experimento walk-forward (SIN fuga): mejora del modelo SOLO-2026.

Compara el modelo actual (forma de goles) contra un Elo-2026 que se construye
SOLO con partidos de 2026, actualizándose partido a partido (jamás ve el futuro
ni aprende el marcador del partido que predice). Prueba escalas y K.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from scipy.stats import poisson

ROOT = os.path.dirname(os.path.dirname(__file__))
RHO = -0.12
TORNEOS = {"Friendly", "FIFA World Cup", "FIFA Series", "CONCACAF Series",
           "FIFA World Cup qualification", "African Cup of Nations", "Unity Cup",
           "Baltic Cup", "Tri-Nations Cup", "Mukuru 4 Nations"}


def dc(lh, la):
    ph = poisson.pmf(np.arange(9), lh); pa = poisson.pmf(np.arange(9), la)
    g = np.outer(ph, pa)
    g[0, 0] *= 1 - lh * la * RHO; g[0, 1] *= 1 + lh * RHO
    g[1, 0] *= 1 + la * RHO; g[1, 1] *= 1 - RHO
    ii, jj = np.indices(g.shape)
    return np.array([g[ii > jj].sum(), g[ii == jj].sum(), g[ii < jj].sum()])


def load():
    r = pd.read_csv(os.path.join(ROOT, "data_repo", "results.csv"), parse_dates=["date"])
    r = r[(r["date"] >= "2026-01-01") & r["tournament"].isin(TORNEOS)].copy()
    r = r.dropna(subset=["home_score", "away_score"]).sort_values("date").reset_index(drop=True)
    r["home_score"] = r["home_score"].astype(int); r["away_score"] = r["away_score"].astype(int)
    return r


def run_elo(r, scale=900, k_comp=40, k_friendly=15, ha=55):
    """Elo-2026 walk-forward. Devuelve (acc_global, acc_wc, n_wc)."""
    elo = {}
    G = {}  # partidos jugados (para 'desde el 2do')
    hits = tot = wc_h = wc_n = 0
    for x in r.itertuples(index=False):
        h, a = x.home_team, x.away_team
        eh = elo.get(h, 1500) + (0 if getattr(x, "neutral", False) else ha)
        ea = elo.get(a, 1500)
        lh = float(np.clip(1.35 * 10 ** ((eh - ea) / scale), 0.2, 5))
        la = float(np.clip(1.35 * 10 ** ((ea - eh) / scale), 0.2, 5))
        o = dc(lh, la); pred = int(o.argmax())
        real = 0 if x.home_score > x.away_score else (2 if x.home_score < x.away_score else 1)
        if G.get(h, 0) >= 1 and G.get(a, 0) >= 1:
            tot += 1; hits += int(pred == real)
            if x.tournament == "FIFA World Cup":
                wc_n += 1; wc_h += int(pred == real)
        # actualizar Elo (después de predecir = sin fuga)
        exp_h = 1 / (1 + 10 ** ((ea - (elo.get(h, 1500) + (0 if getattr(x, "neutral", False) else ha))) / 400))
        sc = 1.0 if real == 0 else (0.5 if real == 1 else 0.0)
        k = k_friendly if x.tournament == "Friendly" else k_comp
        gd = abs(x.home_score - x.away_score)
        k *= 1 + np.log1p(gd) * 0.5
        delta = k * (sc - exp_h)
        elo[h] = elo.get(h, 1500) + delta
        elo[a] = elo.get(a, 1500) - delta
        G[h] = G.get(h, 0) + 1; G[a] = G.get(a, 0) + 1
    return hits / tot * 100, (wc_h / wc_n * 100 if wc_n else 0), wc_n


def main():
    r = load()
    print(f"Partidos 2026: {len(r)}\n")
    print(f"{'Config':<34}{'Global':>9}{'Mundial':>9}")
    # baseline: forma de goles (modelo actual)
    from validate_2026 import main as v
    base = v(quiet=True)
    print(f"{'ACTUAL (forma de goles)':<34}{base[0]:>8.1f}%{base[1]:>8.0f}%")
    best = None
    for scale in (700, 800, 900, 1000, 1100):
        for kf in (10, 15, 25):
            g, w, n = run_elo(r, scale=scale, k_friendly=kf)
            tag = f"Elo2026 scale={scale} kFriendly={kf}"
            print(f"{tag:<34}{g:>8.1f}%{w:>8.0f}%")
            score = 0.5 * g + 0.5 * w   # priorizar ambos
            if best is None or score > best[0]:
                best = (score, scale, kf, g, w)
    print(f"\nMEJOR Elo2026: scale={best[1]} kFriendly={best[2]} -> global {best[3]:.1f}% / Mundial {best[4]:.0f}%")


if __name__ == "__main__":
    main()
