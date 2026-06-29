"""Walk-forward (sin fuga): ¿bajar el peso de amistosos en la forma 2026 mejora?
Prueba pesos de amistoso en la media móvil de goles y mide acierto (global y WC).
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from scipy.stats import poisson

ROOT = os.path.dirname(os.path.dirname(__file__))
RHO = -0.12; HA = 1.10; AVG = 1.35
TORNEOS = {"Friendly", "FIFA World Cup", "FIFA Series", "CONCACAF Series",
           "FIFA World Cup qualification", "African Cup of Nations", "Unity Cup",
           "Baltic Cup", "Tri-Nations Cup", "Mukuru 4 Nations"}


def dc(lh, la):
    g = np.outer(poisson.pmf(np.arange(9), lh), poisson.pmf(np.arange(9), la))
    g[0, 0] *= 1 - lh * la * RHO; g[0, 1] *= 1 + lh * RHO
    g[1, 0] *= 1 + la * RHO; g[1, 1] *= 1 - RHO
    ii, jj = np.indices(g.shape)
    return np.array([g[ii > jj].sum(), g[ii == jj].sum(), g[ii < jj].sum()])


def run(r, fw=1.0):
    """fw = peso de un amistoso en la forma (1.0 = actual)."""
    gf, ga, wsum = {}, {}, {}
    hits = tot = wc_h = wc_n = 0
    for x in r.itertuples(index=False):
        h, a = x.home_team, x.away_team
        def form(t):
            if wsum.get(t, 0) <= 0:
                return AVG, AVG
            return gf[t] / wsum[t], ga[t] / wsum[t]
        hgf, hga = form(h); agf, aga = form(a)
        lh = (hgf + aga) / 2; la = (agf + hga) / 2
        if not getattr(x, "neutral", False):
            lh *= HA; la /= HA
        lh = float(np.clip(lh, 0.15, 5)); la = float(np.clip(la, 0.15, 5))
        o = dc(lh, la); pred = int(o.argmax())
        real = 0 if x.home_score > x.away_score else (2 if x.home_score < x.away_score else 1)
        if wsum.get(h, 0) > 0 and wsum.get(a, 0) > 0:
            tot += 1; hits += int(pred == real)
            if x.tournament == "FIFA World Cup":
                wc_n += 1; wc_h += int(pred == real)
        w = fw if x.tournament == "Friendly" else 1.0
        gf[h] = gf.get(h, 0) + w * x.home_score; ga[h] = ga.get(h, 0) + w * x.away_score
        gf[a] = gf.get(a, 0) + w * x.away_score; ga[a] = ga.get(a, 0) + w * x.home_score
        wsum[h] = wsum.get(h, 0) + w; wsum[a] = wsum.get(a, 0) + w
    return hits / tot * 100, (wc_h / wc_n * 100 if wc_n else 0)


def main():
    r = pd.read_csv(os.path.join(ROOT, "data_repo", "results.csv"), parse_dates=["date"])
    r = r[(r["date"] >= "2026-01-01") & r["tournament"].isin(TORNEOS)].copy()
    r = r.dropna(subset=["home_score", "away_score"]).sort_values("date").reset_index(drop=True)
    r["home_score"] = r["home_score"].astype(int); r["away_score"] = r["away_score"].astype(int)
    print(f"Partidos 2026: {len(r)}\n{'peso amistoso':<16}{'Global':>9}{'Mundial':>9}")
    best = None
    for fw in (1.0, 0.7, 0.5, 0.3, 0.15, 0.0):
        g, w = run(r, fw)
        mark = "  <- actual" if fw == 1.0 else ""
        print(f"{fw:<16}{g:>8.1f}%{w:>8.0f}%{mark}")
        if best is None or (w, g) > (best[1], best[2]):
            best = (fw, w, g)
    print(f"\nMEJOR: peso amistoso={best[0]} -> Mundial {best[1]:.0f}% / global {best[2]:.1f}%")


if __name__ == "__main__":
    main()
