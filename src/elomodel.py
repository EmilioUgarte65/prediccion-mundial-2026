"""Modelo probabilístico 1-X-2 basado en Elo (con curva de empate empírica).

El Elo da la 'expectativa' (victoria + ½ empate). Para separar el empate,
ajustamos P(empate) como función de la diferencia de Elo efectiva, estimada
SOLO con datos anteriores (sin fuga). Es el modelo más simple y robusto, y suele
ser muy competitivo en partidos de selecciones.
"""
from __future__ import annotations

import numpy as np

from ratings import HOME_ADV_ELO

# bordes de |diff Elo efectiva| para la curva de empate
_BINS = np.array([0, 40, 80, 120, 160, 220, 300, 1e9])


class EloModel:
    def __init__(self):
        self.draw_by_bin = np.full(len(_BINS) - 1, 0.25)

    def fit(self, elo_home, elo_away, neutral, labels):
        """Ajusta P(empate) por tramo de diferencia de Elo efectiva."""
        diff = elo_home - elo_away + np.where(neutral, 0.0, HOME_ADV_ELO)
        adiff = np.abs(diff)
        is_draw = (labels == 1).astype(float)
        idx = np.clip(np.digitize(adiff, _BINS) - 1, 0, len(_BINS) - 2)
        for b in range(len(_BINS) - 1):
            m = idx == b
            if m.sum() >= 30:
                self.draw_by_bin[b] = float(is_draw[m].mean())
        return self

    def _pdraw(self, adiff):
        b = int(np.clip(np.digitize([adiff], _BINS)[0] - 1, 0, len(_BINS) - 2))
        return self.draw_by_bin[b]

    def outcome_probs(self, elo_home, elo_away, neutral=True):
        diff = elo_home - elo_away + (0.0 if neutral else HOME_ADV_ELO)
        e = 1.0 / (1.0 + 10 ** (-diff / 400.0))     # expectativa local
        pd = self._pdraw(abs(diff))
        ph = e - pd / 2.0
        pa = (1 - e) - pd / 2.0
        p = np.clip(np.array([ph, pd, pa]), 1e-4, None)
        return p / p.sum()
