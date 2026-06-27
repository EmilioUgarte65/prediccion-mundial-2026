"""Modelo XGBoost: resultado (H/D/A) + goles esperados (regresión Poisson).

Combina los ratings (Elo + ataque/defensa) con forma reciente y contexto del
partido. El simulador usa los dos regresores Poisson (lambda local/visita) como
motor de goles; el clasificador se entrena además como validación de calidad.
"""
from __future__ import annotations

from collections import deque, defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from xgboost import XGBClassifier, XGBRegressor

from ratings import compute_elo, GoalsModel, TOURNAMENT_K, DEFAULT_K
import geo

FORM_N = 5  # partidos para la forma reciente
GLOBAL_PENSHARE = 0.068  # 6.8% de los goles son de penal

FEATURES = [
    "elo_home", "elo_away", "elo_diff",
    "lam_h", "lam_a", "lam_diff",
    "neutral", "tourn_w",
    "home_ppg", "away_ppg",
    "home_gf", "home_ga", "away_gf", "away_ga",
    "home_rest", "away_rest",
    "altitude", "travel_home", "travel_away",   # geo (calculado)
]
# Probados y DESCARTADOS por no mejorar el acierto (techo ~57%): penshare, h2h.
# NOTA: se probó "home/away_penshare" (dependencia del penal) y NO mejoró el
# acierto (XGBoost 55.9% -> 55.6%), así que se descartó. Ver build_penalty_lookup.


def build_penalty_lookup():
    """Por equipo: arrays (fechas, pen_acum, total_acum) de sus goles."""
    from data_prep import load_goalscorers
    g = load_goalscorers()
    g = g[g["own_goal"] != True].sort_values("date")  # noqa: E712
    per = {}
    for team, grp in g.groupby("team"):
        dates = grp["date"].to_numpy()
        pens = (grp["penalty"] == True).to_numpy().cumsum()  # noqa: E712
        tot = np.arange(1, len(grp) + 1)
        per[team] = (dates, pens, tot)
    return per


def penshare_before(per, team, date, prior=8):
    """Fracción de goles de penal del equipo ANTES de la fecha (sin fuga)."""
    if team not in per:
        return GLOBAL_PENSHARE
    dates, pens, tot = per[team]
    idx = int(np.searchsorted(dates, np.datetime64(date)))  # estrictamente antes
    if idx == 0:
        return GLOBAL_PENSHARE
    p, n = int(pens[idx - 1]), int(tot[idx - 1])
    return (p + prior * GLOBAL_PENSHARE) / (n + prior)


def _tourn_weight(t: str) -> int:
    return TOURNAMENT_K.get(t, DEFAULT_K)


class FeatureBuilder:
    """Construye features pre-partido y mantiene el estado final de cada equipo."""

    def __init__(self, goals_model: GoalsModel):
        self.gm = goals_model
        # estado por equipo (se actualiza cronológicamente)
        self.recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=FORM_N))
        self.last_date: dict[str, pd.Timestamp] = {}
        self.last_city: dict[str, str] = {}
        self.h2h: dict[tuple, dict] = {}

    def _h2h(self, h, a):
        rec = self.h2h.get(tuple(sorted((h, a))))
        if not rec:
            return 0.0
        wh, wa, d = rec.get(h, 0), rec.get(a, 0), rec.get("d", 0)
        tot = wh + wa + d
        return (wh - wa) / tot if tot else 0.0

    def _form(self, team: str):
        dq = self.recent[team]
        if not dq:
            return 1.0, 1.2, 1.2  # ppg, gf, ga por defecto
        pts = np.mean([r[0] for r in dq])
        gf = np.mean([r[1] for r in dq])
        ga = np.mean([r[2] for r in dq])
        return pts, gf, ga

    def _rest(self, team: str, date: pd.Timestamp) -> float:
        if team not in self.last_date:
            return 30.0
        d = (date - self.last_date[team]).days
        return float(min(max(d, 1), 120))

    def build_training(self, results: pd.DataFrame) -> pd.DataFrame:
        """Genera el DataFrame de features para todos los partidos (con Elo ya
        calculado) en orden cronológico, actualizando la forma sobre la marcha.
        Además añade lam_h/lam_a por lote.
        """
        # lambdas por lote (rápido)
        lam_h, lam_a = self._batch_lambdas(results)
        results = results.copy()
        results["lam_h"] = lam_h
        results["lam_a"] = lam_a

        feats = {f: np.empty(len(results)) for f in FEATURES}
        for i, row in enumerate(results.itertuples(index=False)):
            h, a, date = row.home_team, row.away_team, row.date
            city = getattr(row, "city", None) or ""
            hp, hgf, hga = self._form(h)
            ap, agf, aga = self._form(a)
            feats["altitude"][i] = geo.altitude(city)
            feats["travel_home"][i] = geo.haversine_km(self.last_city.get(h, city), city)
            feats["travel_away"][i] = geo.haversine_km(self.last_city.get(a, city), city)
            feats["elo_home"][i] = row.home_elo
            feats["elo_away"][i] = row.away_elo
            feats["elo_diff"][i] = row.home_elo - row.away_elo
            feats["lam_h"][i] = row.lam_h
            feats["lam_a"][i] = row.lam_a
            feats["lam_diff"][i] = row.lam_h - row.lam_a
            feats["neutral"][i] = 1.0 if row.neutral else 0.0
            feats["tourn_w"][i] = _tourn_weight(row.tournament)
            feats["home_ppg"][i] = hp
            feats["away_ppg"][i] = ap
            feats["home_gf"][i] = hgf
            feats["home_ga"][i] = hga
            feats["away_gf"][i] = agf
            feats["away_ga"][i] = aga
            feats["home_rest"][i] = self._rest(h, date)
            feats["away_rest"][i] = self._rest(a, date)
            # actualizar estado tras el partido
            self._update(h, a, row.home_score, row.away_score, date)
            self.last_city[h] = city
            self.last_city[a] = city

        out = pd.DataFrame(feats)
        out["home_score"] = results["home_score"].to_numpy()
        out["away_score"] = results["away_score"].to_numpy()
        # etiqueta de resultado: 0=local,1=empate,2=visita
        res = np.where(results["home_score"] > results["away_score"], 0,
                       np.where(results["home_score"] < results["away_score"], 2, 1))
        out["label"] = res
        return out

    def _update(self, h, a, hs, as_, date):
        hp = 3 if hs > as_ else (1 if hs == as_ else 0)
        ap = 3 if as_ > hs else (1 if hs == as_ else 0)
        self.recent[h].append((hp, hs, as_))
        self.recent[a].append((ap, as_, hs))
        self.last_date[h] = date
        self.last_date[a] = date
        key = tuple(sorted((h, a)))
        rec = self.h2h.setdefault(key, {})
        if hs > as_:
            rec[h] = rec.get(h, 0) + 1
        elif as_ > hs:
            rec[a] = rec.get(a, 0) + 1
        else:
            rec["d"] = rec.get("d", 0) + 1

    def _batch_lambdas(self, results):
        gm = self.gm
        home = results["home_team"].to_numpy()
        away = results["away_team"].to_numpy()
        is_home = np.where(results["neutral"].to_numpy(), 0.0, 1.0)
        Xh = gm._build_design(home, away, is_home)
        Xa = gm._build_design(away, home, np.zeros(len(results)))
        lh = np.clip(gm.model.predict(Xh), 0.15, 6.0)
        la = np.clip(gm.model.predict(Xa), 0.15, 6.0)
        return lh, la

    # ---- features para un cruce futuro (usa estado final + ratings actuales) ----
    def matchup_features(self, home: str, away: str, elo: dict,
                         neutral: bool, tournament: str = "FIFA World Cup",
                         city: str = ""):
        lam_h, lam_a = self.gm.expected_goals(home, away, neutral=neutral)
        eh = elo.get(home, 1500.0)
        ea = elo.get(away, 1500.0)
        hp, hgf, hga = self._form(home)
        ap, agf, aga = self._form(away)
        row = {
            "elo_home": eh, "elo_away": ea, "elo_diff": eh - ea,
            "lam_h": lam_h, "lam_a": lam_a, "lam_diff": lam_h - lam_a,
            "neutral": 1.0 if neutral else 0.0, "tourn_w": _tourn_weight(tournament),
            "home_ppg": hp, "away_ppg": ap,
            "home_gf": hgf, "home_ga": hga, "away_gf": agf, "away_ga": aga,
            "home_rest": 4.0, "away_rest": 4.0,  # descanso típico en torneo
            "altitude": geo.altitude(city), "travel_home": 600.0, "travel_away": 600.0,
        }
        return row, lam_h, lam_a


class WCModel:
    def __init__(self):
        self.clf: XGBClassifier | None = None
        self.cal = None  # clasificador calibrado (isotónica)
        self.reg_home: XGBRegressor | None = None
        self.reg_away: XGBRegressor | None = None
        self.metrics: dict = {}

    def train(self, feats: pd.DataFrame, valid_frac: float = 0.15):
        X = feats[FEATURES]
        n = len(feats)
        split = int(n * (1 - valid_frac))
        Xtr, Xva = X.iloc[:split], X.iloc[split:]
        ytr, yva = feats["label"].iloc[:split], feats["label"].iloc[split:]

        self.clf = XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.04,
            subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
            objective="multi:softprob", num_class=3, eval_metric="mlogloss",
            reg_lambda=1.5, n_jobs=-1,
        )
        self.clf.fit(Xtr, ytr)
        proba = self.clf.predict_proba(Xva)
        self.metrics["accuracy"] = float(accuracy_score(yva, proba.argmax(1)))
        self.metrics["log_loss"] = float(log_loss(yva, proba, labels=[0, 1, 2]))

        # Calibración isotónica sobre la validación (mejora calidad de probs)
        try:
            from sklearn.calibration import CalibratedClassifierCV
            try:  # sklearn >= 1.6
                from sklearn.frozen import FrozenEstimator
                base = FrozenEstimator(self.clf)
                self.cal = CalibratedClassifierCV(base, method="isotonic")
            except ImportError:  # sklearn < 1.6
                self.cal = CalibratedClassifierCV(self.clf, method="isotonic", cv="prefit")
            self.cal.fit(Xva, yva)
            pc = self.cal.predict_proba(Xva)
            self.metrics["log_loss_cal"] = float(log_loss(yva, pc, labels=[0, 1, 2]))
        except Exception as e:  # noqa: BLE001
            print("  (calibración no aplicada:", e, ")")
            self.cal = None

        # regresores Poisson de goles (motor de la simulación)
        common = dict(n_estimators=350, max_depth=4, learning_rate=0.04,
                      subsample=0.85, colsample_bytree=0.85, min_child_weight=3,
                      objective="count:poisson", reg_lambda=1.5, n_jobs=-1)
        self.reg_home = XGBRegressor(**common)
        self.reg_away = XGBRegressor(**common)
        self.reg_home.fit(Xtr, feats["home_score"].iloc[:split])
        self.reg_away.fit(Xtr, feats["away_score"].iloc[:split])
        # MAE de goles en validación
        from sklearn.metrics import mean_absolute_error
        self.metrics["goals_mae"] = float(np.mean([
            mean_absolute_error(feats["home_score"].iloc[split:],
                                self.reg_home.predict(Xva)),
            mean_absolute_error(feats["away_score"].iloc[split:],
                                self.reg_away.predict(Xva)),
        ]))
        # los regresores se reentrenan con todo (no necesitan holdout);
        # el clasificador se queda con el split para mantener válida la calibración.
        self.reg_home.fit(X, feats["home_score"])
        self.reg_away.fit(X, feats["away_score"])
        return self

    def predict_lambdas(self, feat_row: dict) -> tuple[float, float]:
        X = pd.DataFrame([feat_row])[FEATURES]
        lh = float(np.clip(self.reg_home.predict(X)[0], 0.12, 6.5))
        la = float(np.clip(self.reg_away.predict(X)[0], 0.12, 6.5))
        return lh, la

    def predict_outcome(self, feat_row: dict) -> np.ndarray:
        X = pd.DataFrame([feat_row])[FEATURES]
        clf = self.cal if self.cal is not None else self.clf
        return clf.predict_proba(X)[0]  # [P_home, P_draw, P_away]


def build_everything():
    """Pipeline de entrenamiento. Devuelve (elo, goals_model, feature_builder, model)."""
    from data_prep import load_results
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    return results, elo, gm, fb, model


if __name__ == "__main__":
    results, elo, gm, fb, model = build_everything()
    print("=== Métricas de validación (XGBoost) ===")
    for k, v in model.metrics.items():
        print(f"  {k}: {v:.4f}")
    # ejemplo de predicción
    row, lh, la = fb.matchup_features("Brazil", "Germany", elo, neutral=True)
    p = model.predict_outcome(row)
    lh2, la2 = model.predict_lambdas(row)
    print("\nBrazil vs Germany (neutral):")
    print(f"  P(local/empate/visita) = {p.round(3)}")
    print(f"  goles esperados XGB: {lh2:.2f} - {la2:.2f}")
