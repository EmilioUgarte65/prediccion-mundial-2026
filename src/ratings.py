"""Sistema de ratings: Elo dinámico + ataque/defensa (Poisson).

- Elo estilo "World Football Elo": ajustado por margen de gol, localía y la
  importancia del torneo. Se calcula cronológicamente sobre TODA la historia.
- Ataque/Defensa: regresión de Poisson (sklearn PoissonRegressor) con dummies
  por selección y ventaja de localía, ponderada por recencia (time-decay).
  Da, para cualquier cruce, los goles esperados (lambda) de cada equipo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import OneHotEncoder

INIT_ELO = 1500.0
HOME_ADV_ELO = 65.0  # puntos Elo de ventaja por jugar en casa (0 si neutral)

# Peso del torneo para el factor K del Elo
TOURNAMENT_K = {
    "FIFA World Cup": 60,
    "FIFA World Cup qualification": 40,
    "UEFA Euro": 50,
    "Copa América": 50,
    "African Cup of Nations": 40,
    "AFC Asian Cup": 40,
    "Gold Cup": 40,
    "UEFA Nations League": 40,
    "Confederations Cup": 45,
    "UEFA Euro qualification": 35,
    "Friendly": 20,
}
DEFAULT_K = 30


def _goal_diff_multiplier(goal_diff: int) -> float:
    """Multiplicador G por margen de gol (World Football Elo)."""
    gd = abs(goal_diff)
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8.0


def compute_elo(results: pd.DataFrame, k_scale: float = 1.0,
                hfa_val: float = HOME_ADV_ELO) -> tuple[pd.DataFrame, dict]:
    """Calcula Elo cronológico.

    k_scale escala el factor K del torneo; hfa_val es la ventaja de localía.
    Devuelve (results con columnas home_elo/away_elo ANTES del partido,
    dict de Elo final por equipo).
    """
    elo: dict[str, float] = {}
    home_elos = np.empty(len(results))
    away_elos = np.empty(len(results))

    for i, row in enumerate(results.itertuples(index=False)):
        h, a = row.home_team, row.away_team
        rh = elo.get(h, INIT_ELO)
        ra = elo.get(a, INIT_ELO)
        home_elos[i] = rh
        away_elos[i] = ra

        hfa = 0.0 if getattr(row, "neutral") else hfa_val
        e_home = 1.0 / (1.0 + 10 ** ((ra - rh - hfa) / 400.0))

        if row.home_score > row.away_score:
            w_home = 1.0
        elif row.home_score < row.away_score:
            w_home = 0.0
        else:
            w_home = 0.5

        k = TOURNAMENT_K.get(row.tournament, DEFAULT_K) * k_scale
        g = _goal_diff_multiplier(row.home_score - row.away_score)
        delta = k * g * (w_home - e_home)
        elo[h] = rh + delta
        elo[a] = ra - delta

    results = results.copy()
    results["home_elo"] = home_elos
    results["away_elo"] = away_elos
    return results, elo


def elo_win_prob(elo_home: float, elo_away: float, neutral: bool = True) -> float:
    hfa = 0.0 if neutral else HOME_ADV_ELO
    return 1.0 / (1.0 + 10 ** ((elo_away - elo_home - hfa) / 400.0))


class GoalsModel:
    """Modelo de goles esperados (ataque/defensa) vía Poisson.

    lambda_local  = exp(intercept + atk[local]  + def_rival + home_effect*es_local)
    lambda_visita = exp(intercept + atk[visita] + def_rival)
    """

    def __init__(self, half_life_years: float = 4.0, alpha: float = 1e-3):
        self.half_life_years = half_life_years
        self.alpha = alpha
        self.model: PoissonRegressor | None = None
        self.enc_atk: OneHotEncoder | None = None
        self.enc_def: OneHotEncoder | None = None
        self.teams: set[str] = set()
        self.base_lambda = 1.3

    def _build_design(self, attack_team, defense_team, is_home):
        atk = self.enc_atk.transform(np.asarray(attack_team).reshape(-1, 1))
        dfn = self.enc_def.transform(np.asarray(defense_team).reshape(-1, 1))
        home = np.asarray(is_home, dtype=float).reshape(-1, 1)
        return np.hstack([atk, dfn, home])

    def fit(self, results: pd.DataFrame, since_years: float = 14.0):
        ref_date = results["date"].max()
        cutoff = ref_date - pd.Timedelta(days=int(since_years * 365.25))
        df = results[results["date"] >= cutoff].copy()

        # Dos filas por partido (perspectiva de cada equipo que anota)
        rows_attack = pd.concat([df["home_team"], df["away_team"]], ignore_index=True)
        rows_defense = pd.concat([df["away_team"], df["home_team"]], ignore_index=True)
        rows_goals = pd.concat([df["home_score"], df["away_score"]], ignore_index=True)
        rows_home = pd.concat([
            (~df["neutral"]).astype(float),         # local con ventaja
            pd.Series(np.zeros(len(df))),           # visitante
        ], ignore_index=True)
        # Ponderación por recencia
        age_days = (ref_date - pd.concat([df["date"], df["date"]],
                                         ignore_index=True)).dt.days
        weights = 0.5 ** (age_days / (self.half_life_years * 365.25))

        self.enc_atk = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self.enc_def = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self.enc_atk.fit(rows_attack.to_numpy().reshape(-1, 1))
        self.enc_def.fit(rows_defense.to_numpy().reshape(-1, 1))
        self.teams = set(rows_attack.unique())
        self.base_lambda = float(rows_goals.mean())

        X = self._build_design(rows_attack, rows_defense, rows_home)
        y = rows_goals.to_numpy()

        self.model = PoissonRegressor(alpha=self.alpha, max_iter=2000)
        self.model.fit(X, y, sample_weight=weights.to_numpy())
        return self

    def expected_goals(self, home_team: str, away_team: str,
                       neutral: bool = True) -> tuple[float, float]:
        is_home_home = 0.0 if neutral else 1.0
        Xh = self._build_design([home_team], [away_team], [is_home_home])
        Xa = self._build_design([away_team], [home_team], [0.0])
        lam_h = float(self.model.predict(Xh)[0])
        lam_a = float(self.model.predict(Xa)[0])
        # límites de seguridad
        lam_h = float(np.clip(lam_h, 0.15, 6.0))
        lam_a = float(np.clip(lam_a, 0.15, 6.0))
        return lam_h, lam_a

    def attack_defense_table(self) -> pd.DataFrame:
        """Tabla interpretable de ataque/defensa relativa por equipo."""
        teams = sorted(self.teams)
        atk, dfn = [], []
        for t in teams:
            lh, _ = self.expected_goals(t, "__avg__", neutral=True)
        # Ataque: goles esperados vs rival promedio; Defensa: goles concedidos
        rows = []
        for t in teams:
            lam_atk, _ = self.expected_goals(t, teams[0], neutral=True)
            rows.append({"team": t})
        return pd.DataFrame(rows)


if __name__ == "__main__":
    from data_prep import load_results
    r = load_results()
    r, elo = compute_elo(r)
    top = sorted(elo.items(), key=lambda kv: kv[1], reverse=True)[:20]
    print("=== TOP 20 ELO (actual) ===")
    for t, e in top:
        print(f"  {t:<22} {e:7.1f}")
    gm = GoalsModel().fit(r)
    print("\n=== Goles esperados de ejemplo (neutral) ===")
    for h, a in [("Brazil", "Argentina"), ("Spain", "Germany"),
                 ("Mexico", "United States"), ("France", "Morocco")]:
        lh, la = gm.expected_goals(h, a, neutral=True)
        print(f"  {h} {lh:.2f} - {la:.2f} {a}")
