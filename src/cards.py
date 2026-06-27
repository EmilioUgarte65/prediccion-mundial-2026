"""Modelo de tarjetas por equipo (a partir de StatsBomb 2018/2022).

Estima las amarillas/rojas esperadas de cada equipo en un partido, usando su
tendencia disciplinaria histórica (con encogimiento hacia el promedio global
para equipos con pocos datos). Para equipos sin historial -> promedio global.

Limitación honesta: solo hay datos de Mundiales 2018/2022 (plantillas distintas),
así que es una TENDENCIA, no una predicción exacta.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
STATS = os.path.join(ROOT, "data_user", "sb_match_stats.csv")
PRIOR_N = 6  # fuerza del encogimiento hacia el promedio


class CardModel:
    def __init__(self):
        self.global_yellow = 1.68
        self.global_red = 0.031
        self.factor = {}   # team -> multiplicador de amarillas vs promedio

    def fit(self):
        if not os.path.exists(STATS):
            return self
        ysum = defaultdict(int); rsum = defaultdict(int); cnt = defaultdict(int)
        ty = tr = n2 = 0
        with open(STATS, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for side in ("home", "away"):
                    t = r[f"{side}_team"]
                    ysum[t] += int(r[f"{side}_yellow"]); rsum[t] += int(r[f"{side}_red"])
                    cnt[t] += 1
                ty += int(r["home_yellow"]) + int(r["away_yellow"])
                tr += int(r["home_red"]) + int(r["away_red"]); n2 += 2
        if n2:
            self.global_yellow = ty / n2
            self.global_red = tr / n2
        for t in cnt:
            shrunk = (ysum[t] + PRIOR_N * self.global_yellow) / (cnt[t] + PRIOR_N)
            self.factor[t] = shrunk / self.global_yellow
        return self

    def red_rate(self, team):
        """Prob. de que el equipo reciba una roja en un partido (acotada)."""
        f = self.factor.get(team, 1.0)
        return min(0.18, self.global_red * f)

    def expected(self, team_a, team_b, knockout=False):
        """Amarillas y rojas esperadas (A, B). Eliminatoria sube ~10% la intensidad."""
        inten = 1.1 if knockout else 1.0
        fa = self.factor.get(team_a, 1.0)
        fb = self.factor.get(team_b, 1.0)
        ya = round(self.global_yellow * fa * inten, 1)
        yb = round(self.global_yellow * fb * inten, 1)
        ra = round(self.global_red * fa, 3)
        rb = round(self.global_red * fb, 3)
        return {"yellowA": ya, "yellowB": yb, "redA": ra, "redB": rb}


if __name__ == "__main__":
    cm = CardModel().fit()
    print(f"Promedio: {cm.global_yellow:.2f} amarillas, {cm.global_red:.3f} rojas/equipo")
    for a, b in [("Argentina", "Spain"), ("Mexico", "Germany"), ("Brazil", "Croatia")]:
        print(a, "vs", b, "->", cm.expected(a, b))
