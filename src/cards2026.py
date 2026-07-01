"""Modelo de tarjetas CALIBRADO A 2026 (reemplaza el prior de Mundiales 2018/22,
que sobreestimaba ~+0.9 tarjetas/partido).

Usa la tasa de amarillas por equipo de ESTE Mundial (ESPN), con encogimiento hacia
la media global 2026. Sin fuga: para validar se usa walk-forward (solo partidos
previos); para predecir partidos FUTUROS se usan todas las tasas ya observadas.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
STATS = os.path.join(ROOT, "data_user", "match_team_stats_2026.csv")


def _load_games():
    """Partidos 2026 ordenados por fecha: [{date, teams:[(team,yellow,red),...]}]."""
    byg = {}
    if not os.path.exists(STATS):
        return []
    for r in csv.DictReader(open(STATS, encoding="utf-8")):
        g = r["gameId"]
        byg.setdefault(g, {"date": r["date"], "teams": []})
        byg[g]["teams"].append((r["team"], int(float(r["yellowCards"] or 0)),
                                int(float(r["redCards"] or 0))))
    games = [v for v in byg.values() if len(v["teams"]) == 2]
    games.sort(key=lambda x: x["date"])
    return games


class Card2026:
    """Tarjetas esperadas por equipo, calibrado con datos reales de 2026."""

    def __init__(self, K=8):
        self.K = K
        self.global_yellow = 1.23   # media 2026 por equipo (se recalcula en fit)
        self.global_red = 0.05
        self.yhist = defaultdict(list)
        self.factor = {}            # compat con CardModel (multiplicador)

    def fit(self):
        games = _load_games()
        ys = []; rs = []
        for x in games:
            for (t, y, r) in x["teams"]:
                self.yhist[t].append(y); ys.append(y); rs.append(r)
        if ys:
            self.global_yellow = sum(ys) / len(ys)
            self.global_red = max(0.01, sum(rs) / len(rs))
        for t, h in self.yhist.items():
            rate = (sum(h) + self.K * self.global_yellow) / (len(h) + self.K)
            self.factor[t] = rate / self.global_yellow
        return self

    def _rate(self, t):
        h = self.yhist.get(t)
        if not h:
            return self.global_yellow
        return (sum(h) + self.K * self.global_yellow) / (len(h) + self.K)

    def red_rate(self, team):
        return min(0.18, self.global_red * self.factor.get(team, 1.0))

    def expected(self, team_a, team_b, knockout=False):
        inten = 1.05 if knockout else 1.0   # KO sube un poco la intensidad
        ya = round(self._rate(team_a) * inten, 1)
        yb = round(self._rate(team_b) * inten, 1)
        ra = round(self.global_red * self.factor.get(team_a, 1.0), 3)
        rb = round(self.global_red * self.factor.get(team_b, 1.0), 3)
        return {"yellowA": ya, "yellowB": yb, "redA": ra, "redB": rb}


def walkforward_ou(line=3.5, K=8):
    """Acierto Over/Under de tarjetas TOTALES walk-forward (sin fuga) para validar."""
    from scipy.stats import poisson
    games = _load_games()
    hist = defaultdict(list); napp = defaultdict(int)
    run = 0.0; seen = 0
    ou = 0; mae = 0.0; bias = 0.0; n = 0
    for x in games:
        (ta, ya, _), (tb, yb, _) = x["teams"]
        g = (run / seen) if seen else 1.23

        def rate(t):
            h = hist[t]
            return (sum(h) + K * g) / (len(h) + K)
        pred = rate(ta) + rate(tb); real = ya + yb
        if napp[ta] >= 1 and napp[tb] >= 1:
            ou += int(((1 - poisson.cdf(int(line), pred)) > 0.5) == (real > line))
            mae += abs(round(pred) - real); bias += pred - real; n += 1
        hist[ta].append(ya); hist[tb].append(yb)
        napp[ta] += 1; napp[tb] += 1
        run += ya + yb; seen += 2
    n = max(1, n)
    return {"ou_acc": round(ou / n, 4), "mae": round(mae / n, 3),
            "bias": round(bias / n, 3), "n": n}


if __name__ == "__main__":
    cm = Card2026().fit()
    print(f"Media 2026: {cm.global_yellow:.2f} amarillas/equipo ({cm.global_yellow*2:.2f}/partido)")
    print("walk-forward O/U 3.5:", walkforward_ou())
    for a, b in [("Argentina", "France"), ("Spain", "Austria")]:
        print(a, "vs", b, "->", cm.expected(a, b))
