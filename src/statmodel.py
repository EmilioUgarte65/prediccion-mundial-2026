"""Modelo ESTADÍSTICO: Poisson bivariado de Dixon-Coles.

A partir de los goles esperados (lambda) del modelo de ataque/defensa, calcula
analíticamente la matriz de marcadores con la corrección de Dixon-Coles para
resultados bajos (0-0, 1-0, 0-1, 1-1) y de ahí las probabilidades 1-X-2.

No usa machine learning: es el enfoque estadístico clásico del fútbol.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

from ratings import GoalsModel

MAXG = 10


def _tau(x, y, lh, la, rho):
    """Corrección de Dixon-Coles para marcadores bajos."""
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


class StatModel:
    def __init__(self, goals_model: GoalsModel, rho: float = -0.05):
        self.gm = goals_model
        self.rho = rho
        # matriz tau base (solo difiere en las 4 esquinas, depende de lh/la)
        self._idx = np.arange(MAXG + 1)

    def score_matrix(self, lh: float, la: float) -> np.ndarray:
        ph = poisson.pmf(self._idx, lh)
        pa = poisson.pmf(self._idx, la)
        grid = np.outer(ph, pa)
        r = self.rho
        grid[0, 0] *= 1 - lh * la * r
        grid[0, 1] *= 1 + lh * r
        grid[1, 0] *= 1 + la * r
        grid[1, 1] *= 1 - r
        grid = np.clip(grid, 1e-12, None)
        return grid / grid.sum()

    def outcome_from_lambdas(self, lh: float, la: float) -> np.ndarray:
        g = self.score_matrix(lh, la)
        ii, jj = np.indices(g.shape)
        return np.array([g[ii > jj].sum(), g[ii == jj].sum(), g[ii < jj].sum()])

    def outcome_probs(self, home, away, neutral=True):
        lh, la = self.gm.expected_goals(home, away, neutral=neutral)
        g = self.score_matrix(lh, la)
        ii, jj = np.indices(g.shape)
        pH = g[ii > jj].sum()
        pD = g[ii == jj].sum()
        pA = g[ii < jj].sum()
        return np.array([pH, pD, pA]), (lh, la)

    def most_likely_score(self, home, away, neutral=True, outcome=None):
        lh, la = self.gm.expected_goals(home, away, neutral=neutral)
        g = self.score_matrix(lh, la)
        if outcome is not None:
            ii, jj = np.indices(g.shape)
            mask = {0: ii > jj, 1: ii == jj, 2: ii < jj}[outcome]
            g = np.where(mask, g, -1)
        i, j = np.unravel_index(g.argmax(), g.shape)
        return int(i), int(j)

    def fit_rho(self, lambdas_h, lambdas_a, labels, grid=None):
        """Ajusta rho minimizando log-loss de 1-X-2 sobre datos dados."""
        if grid is None:
            grid = np.linspace(-0.18, 0.06, 13)
        best, best_ll = self.rho, np.inf
        H = poisson.pmf(self._idx[:, None], lambdas_h[None, :])  # (MAXG+1, N)
        A = poisson.pmf(self._idx[:, None], lambdas_a[None, :])
        ii, jj = np.indices((MAXG + 1, MAXG + 1))
        hmask, dmask, amask = ii > jj, ii == jj, ii < jj
        for r in grid:
            ll = 0.0
            for k in range(len(labels)):
                g = np.outer(H[:, k], A[:, k])
                lh, la = lambdas_h[k], lambdas_a[k]
                g[0, 0] *= 1 - lh * la * r; g[0, 1] *= 1 + lh * r
                g[1, 0] *= 1 + la * r; g[1, 1] *= 1 - r
                g = np.clip(g, 1e-12, None); g /= g.sum()
                p = (g[hmask].sum(), g[dmask].sum(), g[amask].sum())
                ll -= np.log(max(p[labels[k]], 1e-12))
            if ll < best_ll:
                best_ll, best = ll, r
        self.rho = float(best)
        return self.rho
