"""Modelo de tiempos de gol a partir de goalscorers.csv.

Construye la distribución empírica del minuto en que caen los goles y permite
muestrear minutos realistas para los goles simulados de un partido.
También expone la distribución por tramos para mostrar "en qué minuto es más
probable que anote cada equipo".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_prep import load_goalscorers

# Tramos para mostrar en la web (cada 15')
BUCKETS = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75), (76, 90)]
BUCKET_LABELS = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"]


class GoalTimingModel:
    def __init__(self):
        # probabilidad por minuto 1..90 (tiempo reglamentario)
        self.minute_pmf = np.full(90, 1.0 / 90)
        self.bucket_probs = np.full(len(BUCKETS), 1.0 / len(BUCKETS))

    def fit(self, goals: pd.DataFrame | None = None):
        if goals is None:
            goals = load_goalscorers()
        reg = goals[(goals["minute"] >= 1) & (goals["minute"] <= 90)]["minute"]
        counts = np.zeros(90)
        for m in reg:
            counts[int(m) - 1] += 1
        # Los goles marcados en tiempo añadido se registran como 45 y 90:
        # suavizamos un poco para no sobre-representar esos minutos exactos.
        counts = self._smooth(counts)
        self.minute_pmf = counts / counts.sum()

        # Probabilidad por tramo de 15'
        bucket = np.zeros(len(BUCKETS))
        for i, (lo, hi) in enumerate(BUCKETS):
            bucket[i] = self.minute_pmf[lo - 1:hi].sum()
        self.bucket_probs = bucket / bucket.sum()
        return self

    @staticmethod
    def _smooth(counts: np.ndarray, window: int = 3) -> np.ndarray:
        kernel = np.ones(window) / window
        return np.convolve(counts, kernel, mode="same") + 1e-6

    def sample_minutes(self, n_goals: int, rng: np.random.Generator,
                       extra_time: bool = False) -> list[int]:
        """Muestrea n minutos de gol ordenados.

        extra_time=True genera minutos 91-120 (prórroga) con densidad uniforme.
        """
        if n_goals <= 0:
            return []
        if extra_time:
            mins = rng.integers(91, 121, size=n_goals)
        else:
            mins = rng.choice(np.arange(1, 91), size=n_goals, p=self.minute_pmf)
        return sorted(int(m) for m in mins)

    def bucket_distribution(self) -> dict:
        return {lbl: round(float(p), 4)
                for lbl, p in zip(BUCKET_LABELS, self.bucket_probs)}


if __name__ == "__main__":
    gt = GoalTimingModel().fit()
    print("=== Distribución de goles por tramo (15') ===")
    for lbl, p in gt.bucket_distribution().items():
        bar = "#" * int(p * 100)
        print(f"  {lbl:>6} {p*100:5.1f}% {bar}")
    rng = np.random.default_rng(0)
    print("\nEjemplo de minutos para 3 goles:", gt.sample_minutes(3, rng))
