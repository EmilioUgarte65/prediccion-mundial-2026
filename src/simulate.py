"""Simulador Monte Carlo del Mundial 2026 desde el estado REAL actual.

Estado de los datos: grupos A, B y C completos; grupos D-L con la última jornada
por jugar (18 partidos). El simulador:
  1. predice/simula los partidos de grupo restantes,
  2. completa las tablas y decide clasificados (1º, 2º y 8 mejores terceros),
  3. simula las eliminatorias (R32 -> Final) con prórroga y penales.

Motor de goles: regresores Poisson de XGBoost + ratings. Tiempos de gol:
distribución empírica. Genera web/data/predictions.json.
"""
from __future__ import annotations

import copy
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import poisson

from data_prep import load_results, get_wc2026_fixtures
from wc2026 import load_official_groups, compute_standings, qualifiers
from ratings import compute_elo, GoalsModel, elo_win_prob
from goal_timing import GoalTimingModel, BUCKET_LABELS
from model import FeatureBuilder, WCModel
from cards import CardModel
from players import team_scorers
from bracket import (R32_STRUCTURE, R16_FEED, QF_FEED, SF_FEED, FINAL_FEED,
                     SF_FEED as _SF, resolve_r32_teams)

OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "web", "data", "predictions.json")

N_SIMS = 10000
N_MATCH = 4000
LBL = {0: "1", 1: "X", 2: "2"}


def load_market_odds():
    """Cuotas 1X2 del mercado -> {(home,away): (p1,px,p2)} des-vigorizadas.

    El mercado es el mejor predictor; se usa como señal líder donde existe.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "odds.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                oh, od, oa = float(r["odd_home"]), float(r["odd_draw"]), float(r["odd_away"])
            except (ValueError, KeyError):
                continue
            s = 1 / oh + 1 / od + 1 / oa
            out[(r["home_team"], r["away_team"])] = (1 / oh / s, 1 / od / s, 1 / oa / s)
    return out


def load_player_attack():
    """Multiplicadores bottom-up por equipo: ataque y defensa (jugadores reales)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "team_player_attack.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["team"]] = {"att": float(r["attack_mult"]),
                                  "def": float(r.get("def_mult", 1.0))}
            except (ValueError, KeyError):
                continue
    return out


def load_availability():
    """Fuerza del plantel disponible por equipo (0-100%) -> factor de ataque."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "availability.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["team"]] = float(r["strength_pct"]) / 100.0
            except (ValueError, KeyError):
                continue
    return out


def load_weather_factor():
    """Factor de gol por clima de cada SEDE (calor/lluvia reducen un poco el gol)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "weather.csv")
    if not os.path.exists(path):
        return {}
    import csv
    from collections import defaultdict as dd
    tmaxs = dd(list); rains = dd(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                tmaxs[r["city"]].append(float(r["tmax"]))
                rains[r["city"]].append(float(r["rain_mm"]))
            except (ValueError, KeyError):
                continue
    out = {}
    for city in tmaxs:
        tmax = sum(tmaxs[city]) / len(tmaxs[city])
        rain = sum(rains[city]) / len(rains[city])
        # calor extremo (>32°C) y lluvia fuerte bajan el ritmo (máx ~-6%)
        f = 1.0 - 0.004 * max(0, tmax - 30) - 0.003 * max(0, rain - 5)
        out[city] = round(max(0.94, f), 3)
    return out


def load_fatigue():
    """Fatiga de veteranos por equipo (de web/data/player_performance.json).

    Devuelve {equipo: factor} <=1 (peor fatiga de sus estrellas veteranas).
    """
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "web", "data", "player_performance.json")
    if not os.path.exists(path):
        return {}
    import json
    data = json.load(open(path, encoding="utf-8"))
    worst = {}
    rank = {"alta": 0.96, "media": 0.98, "baja": 1.0}
    for v in data.get("veterans", []):
        f = rank.get(v.get("fatigue"), 1.0)
        worst[v["team"]] = min(worst.get(v["team"], 1.0), f)
    return worst


def load_morale():
    """Índice de ánimo/momentum por equipo (NLP de noticias, -1..+1)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "morale_2026.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["team"]] = {"score": float(r["morale"]), "note": r["note"]}
            except (ValueError, KeyError):
                continue
    return out


def load_injuries():
    """Lesiones/bajas 2026 (investigadas) -> {equipo: [dict]}."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "injuries_2026.csv")
    if not os.path.exists(path):
        return {}
    import csv
    from collections import defaultdict as dd
    out = dd(list)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["team"]].append(r)
    return dict(out)


def injury_factors(team, injuries):
    """(mult_ataque_propio, penal_defensa) según bajas. out pesa más que dudoso."""
    att = deff = 0.0
    for inj in injuries.get(team, []):
        w = 1.0 if inj["status"] == "out" else 0.4
        side = inj["side"]
        if side == "att":
            att += w
        elif side == "mid":
            att += 0.4 * w
        elif side in ("def", "gk"):
            deff += w
    atk_mult = max(0.80, 1 - 0.05 * att)       # baja ataque propio (máx -20%)
    def_pen = min(0.15, 0.04 * deff)            # sube ataque rival (máx +15%)
    return atk_mult, def_pen


def load_pen_share():
    """Fracción histórica de goles de penal por equipo (dato informativo)."""
    from data_prep import load_goalscorers
    g = load_goalscorers()
    g = g[g["own_goal"] != True]  # noqa: E712
    out = {}
    for team, grp in g.groupby("team"):
        n = len(grp)
        if n >= 30:
            out[team] = round(float((grp["penalty"] == True).sum() / n), 3)  # noqa: E712
    return out


def _load_champion_odds():
    """Prob. de campeón implícita del mercado (data_user/champion_odds.csv)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "champion_odds.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["team"]] = float(r["market_champ"])
            except (ValueError, KeyError):
                continue
    return out


def load_team_xg():
    """xG por selección aportado por el usuario (data_user/team_xg.csv).

    Fuente externa (FootyStats). Se usa SOLO para predicciones a futuro
    (mezclado con el modelo) para reducir el sesgo de una sola fuente.
    Devuelve {equipo: (xg_for, xg_against)} o {} si no existe el archivo.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "data_user", "team_xg.csv")
    if not os.path.exists(path):
        return {}
    import csv
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[r["team"]] = (float(r["xg_for"]), float(r["xg_against"]))
            except (ValueError, KeyError):
                continue
    return out


# ------------------------- motor de partidos -------------------------
HOSTS = {"Mexico", "United States", "Canada"}  # anfitriones 2026 (juegan en casa)


class Engine:
    XG_WEIGHT = 0.35    # peso de la señal xG externa al mezclar con el modelo
    ODDS_WEIGHT = 0.6   # peso del mercado donde hay cuotas (señal líder)
    HOST_BOOST = 1.12   # empuje de gol del anfitrión (datos: local WC gana 61% vs 43%)
    GOAL_CAL = 1.06     # calibración: 2026 es goleador (modelo 2.78 vs real 2.95)

    # Pesos de cada señal forward (0 = apagada, 1 = efecto base).
    # TUNEADOS por descenso de coordenadas contra el torneo real 2026
    # (tune_signal_weights.py): MAE 0.825 -> 0.800, exacto 13.3% -> 15.0%.
    # 'inj' y 'avail' el tuner los lleva a 0 en partidos pasados (test sesgado:
    # se aplican datos de HOY a partidos previos); se dejan en un piso pequeño
    # porque para partidos FUTUROS una baja confirmada sí importa.
    W = {"xg": 0.35, "inj": 0.25, "morale": 1.5, "fatigue": 0.5,
         "patt": 1.0, "avail": 0.5, "weather": 0.0}

    def __init__(self, fb, model, elo, timing):
        self.fb, self.model, self.elo, self.timing = fb, model, elo, timing
        self.W = dict(Engine.W)  # copia tuneable por instancia
        self.lam_cache = {}
        self.xg = load_team_xg()
        self.market = load_market_odds()
        self.cards = CardModel().fit()
        self.pen_share = load_pen_share()
        self.scorers = team_scorers()
        self.injuries = load_injuries()
        self.morale = load_morale()
        self.fatigue = load_fatigue()
        self.patt = load_player_attack()  # ataque+defensa bottom-up por jugadores
        if self.patt:
            print(f"  Bottom-up (ataque+defensa) cargado para {len(self.patt)} selecciones.")
        self.avail = load_availability()  # fuerza del plantel disponible
        if self.avail:
            print(f"  Disponibilidad de plantel cargada para {len(self.avail)} selecciones.")
        self.weather = load_weather_factor()  # factor de gol por clima de sede
        if self.weather:
            print(f"  Clima de {len(self.weather)} sedes cargado.")
        if self.injuries:
            print(f"  Lesiones cargadas para {len(self.injuries)} selecciones.")
        if self.morale:
            print(f"  Ánimo (NLP) cargado para {len(self.morale)} selecciones.")
        if self.xg:
            print(f"  xG externo cargado para {len(self.xg)} selecciones "
                  f"(peso {self.XG_WEIGHT}).")
        if self.market:
            print(f"  Cuotas de mercado cargadas para {len(self.market)} partidos "
                  f"(peso {self.ODDS_WEIGHT}).")

    def outcome_blended(self, a, b, neutral=True):
        """1X2 del modelo, mezclado con el mercado si hay cuotas para el partido."""
        m = self.outcome(a, b, neutral)
        mk = self.market.get((a, b))
        if mk is not None:
            w = self.ODDS_WEIGHT
            m = [(1 - w) * m[i] + w * mk[i] for i in range(3)]
            s = sum(m)
            m = np.array([x / s for x in m])
        return np.asarray(m)

    def lambdas(self, a, b, neutral=True):
        key = (a, b, neutral)
        if key not in self.lam_cache:
            row, _, _ = self.fb.matchup_features(a, b, self.elo, neutral=neutral)
            lh, la = self.model.predict_lambdas(row)
            W = self.W
            # Mezcla con xG externo (peso tuneado)
            if a in self.xg and b in self.xg:
                w = W["xg"]
                xgf_a, xga_a = self.xg[a]
                xgf_b, xga_b = self.xg[b]
                lh = (1 - w) * lh + w * (xgf_a + xga_b) / 2.0
                la = (1 - w) * la + w * (xgf_b + xga_a) / 2.0
            # Ventaja de anfitrión 2026 (México/EE.UU./Canadá juegan en casa)
            if a in HOSTS and b not in HOSTS:
                lh *= self.HOST_BOOST; la /= self.HOST_BOOST
            elif b in HOSTS and a not in HOSTS:
                la *= self.HOST_BOOST; lh /= self.HOST_BOOST
            # Lesiones/bajas (peso tuneado): baja ataque propio, sube el del rival
            if self.injuries:
                ata, dpa = injury_factors(a, self.injuries)
                atb, dpb = injury_factors(b, self.injuries)
                lh *= (1 - W["inj"] * (1 - ata)) * (1 + W["inj"] * dpb)
                la *= (1 - W["inj"] * (1 - atb)) * (1 + W["inj"] * dpa)
            # Ánimo/momentum (NLP, peso tuneado): ±5% base por confianza
            if self.morale:
                lh *= 1 + W["morale"] * 0.05 * self.morale.get(a, {}).get("score", 0.0)
                la *= 1 + W["morale"] * 0.05 * self.morale.get(b, {}).get("score", 0.0)
            # Fatiga de veteranos (peso tuneado)
            if self.fatigue:
                lh *= 1 - W["fatigue"] * (1 - self.fatigue.get(a, 1.0))
                la *= 1 - W["fatigue"] * (1 - self.fatigue.get(b, 1.0))
            # Bottom-up: ataque propio + defensa rival (peso tuneado)
            if self.patt:
                pa = self.patt.get(a); pb = self.patt.get(b)
                if pa:
                    lh *= 1 + W["patt"] * 0.5 * (pa["att"] - 1.0)
                    la *= 1 - W["patt"] * 0.5 * (pa["def"] - 1.0)
                if pb:
                    la *= 1 + W["patt"] * 0.5 * (pb["att"] - 1.0)
                    lh *= 1 - W["patt"] * 0.5 * (pb["def"] - 1.0)
            # Disponibilidad de plantel (peso tuneado)
            if self.avail:
                lh *= 1 - W["avail"] * 0.15 * (1 - self.avail.get(a, 1.0))
                la *= 1 - W["avail"] * 0.15 * (1 - self.avail.get(b, 1.0))
            # Clima de sede (peso tuneado; 0 por defecto tras validar)
            if self.weather and W["weather"] > 0:
                wf = sum(self.weather.values()) / len(self.weather)
                lh *= 1 - W["weather"] * (1 - wf); la *= 1 - W["weather"] * (1 - wf)
            # Calibración al ritmo goleador real de 2026
            lh *= self.GOAL_CAL; la *= self.GOAL_CAL
            self.lam_cache[key] = (float(np.clip(lh, 0.12, 6.5)),
                                   float(np.clip(la, 0.12, 6.5)))
        return self.lam_cache[key]

    def outcome(self, a, b, neutral=True):
        row, _, _ = self.fb.matchup_features(a, b, self.elo, neutral=neutral)
        return self.model.predict_outcome(row)

    def outcome_by_model(self, a, b, neutral=True):
        """Prob. 1-X-2 de cada modelo por separado (para el selector en la web)."""
        row, lh, la = self.fb.matchup_features(a, b, self.elo, neutral=neutral)
        xgb = np.asarray(self.model.predict_outcome(row), float)
        out = {"xgb": xgb}
        sm = getattr(self, "statm", None)
        out["stat"] = np.asarray(sm.outcome_from_lambdas(lh, la), float) if sm else xgb
        em = getattr(self, "elom", None)
        out["elo"] = (np.asarray(em.outcome_probs(self.elo.get(a, 1500),
                      self.elo.get(b, 1500), neutral), float) if em else xgb)
        out["ens"] = (out["xgb"] + out["stat"] + out["elo"]) / 3.0
        return {k: [round(float(x), 4) for x in v] for k, v in out.items()}

    def pen_prob(self, a, b):
        # Los penales son casi un volado: con 678 tandas reales, quien patea
        # primero gana 52.7% y el favorito apenas tiene ventaja. Comprimimos
        # la prob. de Elo hacia 50/50 (factor 0.35 -> favorito fuerte ~60% máx).
        e = elo_win_prob(self.elo.get(a, 1500), self.elo.get(b, 1500), True)
        return 0.5 + 0.35 * (e - 0.5)

    def _apply_reds(self, lh, la, a, b, rng):
        """Si cae una roja, ese equipo baja su gol esperado y sube el del rival.
        Efecto conservador (literatura: una roja vale ~0.5-0.8 de dif. de gol)."""
        if rng.random() < self.cards.red_rate(a):
            lh *= 0.80; la *= 1.12
        if rng.random() < self.cards.red_rate(b):
            la *= 0.80; lh *= 1.12
        return lh, la

    def sim_group_match(self, a, b, rng, neutral=True):
        lh, la = self.lambdas(a, b, neutral)
        lh, la = self._apply_reds(lh, la, a, b, rng)
        # Si hay cuotas, sesga el resultado hacia el mercado (mantiene goles realistas)
        if (a, b) in self.market:
            target = int(rng.choice(3, p=self.outcome_blended(a, b, neutral)))
            for _ in range(6):
                gh, ga = int(rng.poisson(lh)), int(rng.poisson(la))
                res = 0 if gh > ga else (2 if gh < ga else 1)
                if res == target:
                    return gh, ga
            return {0: (1, 0), 1: (1, 1), 2: (0, 1)}[target]
        return int(rng.poisson(lh)), int(rng.poisson(la))

    def sim_ko_match(self, a, b, rng):
        lh, la = self.lambdas(a, b, True)
        lh, la = self._apply_reds(lh, la, a, b, rng)
        gh, ga = rng.poisson(lh), rng.poisson(la)
        if gh != ga:
            return (a if gh > ga else b), gh, ga, "regular"
        gh += rng.poisson(lh * 30 / 90); ga += rng.poisson(la * 30 / 90)
        if gh != ga:
            return (a if gh > ga else b), gh, ga, "ET"
        return (a if rng.random() < self.pen_prob(a, b) else b), gh, ga, "pens"


# ------------------------- fase de grupos -------------------------
def base_group_stats(played, groups):
    """Stats acumulados (Pts, GD, GF) de los partidos ya jugados."""
    t2g = {t: g for g, ts in groups.items() for t in ts}
    stats = {t: [0, 0, 0] for t in t2g}  # [Pts, GD, GF]
    for r in played.itertuples(index=False):
        h, a = r.home_team, r.away_team
        hs, as_ = int(r.home_score), int(r.away_score)
        stats[h][1] += hs - as_; stats[h][2] += hs
        stats[a][1] += as_ - hs; stats[a][2] += as_
        if hs > as_:
            stats[h][0] += 3
        elif hs < as_:
            stats[a][0] += 3
        else:
            stats[h][0] += 1; stats[a][0] += 1
    return stats, t2g


def qualify_from_stats(stats, groups, rng):
    """Ordena grupos y devuelve clasificados (con desempate aleatorio fino)."""
    winners, runners, thirds = {}, {}, []
    for g, teams in groups.items():
        ordered = sorted(teams, key=lambda t: (stats[t][0], stats[t][1],
                                               stats[t][2], rng.random()),
                         reverse=True)
        winners[g] = {"team": ordered[0]}
        runners[g] = {"team": ordered[1]}
        thirds.append({"team": ordered[2], "group": g,
                       "Pts": stats[ordered[2]][0], "GD": stats[ordered[2]][1],
                       "GF": stats[ordered[2]][2]})
    thirds_sorted = sorted(thirds, key=lambda d: (d["Pts"], d["GD"], d["GF"],
                                                  rng.random()), reverse=True)
    return {"winners": winners, "runners": runners,
            "best_thirds": thirds_sorted[:8]}


# ------------------------- torneo completo (Monte Carlo) -------------------------
def play_tournament(engine, base_stats, groups, remaining, rng):
    stats = copy.deepcopy(base_stats)
    for m in remaining:
        gh, ga = engine.sim_group_match(m["home"], m["away"], rng, m["neutral"])
        h, a = m["home"], m["away"]
        stats[h][1] += gh - ga; stats[h][2] += gh
        stats[a][1] += ga - gh; stats[a][2] += ga
        if gh > ga:
            stats[h][0] += 3
        elif gh < ga:
            stats[a][0] += 3
        else:
            stats[h][0] += 1; stats[a][0] += 1

    qual = qualify_from_stats(stats, groups, rng)
    r32, _ = resolve_r32_teams(qual)

    reached = {t: 0 for g in groups for t in groups[g]}
    winners = {}
    for mid, (a, b) in r32.items():
        reached[a] = max(reached[a], 1); reached[b] = max(reached[b], 1)
        w, *_ = engine.sim_ko_match(a, b, rng)
        winners[mid] = w; reached[w] = max(reached[w], 2)
    for feed, ph in ((R16_FEED, 3), (QF_FEED, 4), (SF_FEED, 5), (FINAL_FEED, 6)):
        for mid, (fa, fb) in feed.items():
            a, b = winners[fa], winners[fb]
            w, *_ = engine.sim_ko_match(a, b, rng)
            winners[mid] = w; reached[w] = max(reached[w], ph)
    return reached


def monte_carlo(engine, base_stats, groups, remaining, n=N_SIMS, seed=42):
    rng = np.random.default_rng(seed)
    phases = ["Qualify", "R16", "QF", "SF", "Final", "Champion"]
    counts = defaultdict(lambda: np.zeros(6))
    for _ in range(n):
        reached = play_tournament(engine, base_stats, groups, remaining, rng)
        for team, r in reached.items():
            # r: 1=Qualify,2=R16,3=QF,4=SF,5=Final,6=Champion
            for p in range(1, r + 1):
                counts[team][p - 1] += 1
    adv = {}
    for team, c in counts.items():
        adv[team] = {ph: round(float(c[i] / n), 4) for i, ph in enumerate(phases)}
    return adv


# ------------------------- predicciones de partido -------------------------
def most_likely_score(lh, la, maxg=8, outcome=None):
    """Marcador más probable (Poisson + Dixon-Coles). Si outcome in {0,1,2},
    restringe al resultado (0=gana local, 1=empate, 2=gana visita)."""
    grid = _dc_grid(lh, la, maxg)
    if outcome is not None:
        ii, jj = np.indices(grid.shape)
        if outcome == 0:
            grid = np.where(ii > jj, grid, -1)
        elif outcome == 2:
            grid = np.where(ii < jj, grid, -1)
        else:
            grid = np.where(ii == jj, grid, -1)
    i, j = np.unravel_index(grid.argmax(), grid.shape)
    return int(i), int(j)


_RHO = -0.05  # corrección Dixon-Coles (se ajusta en main con datos reales)


def _dc_grid(lh, la, maxg):
    """Rejilla de marcadores con corrección Dixon-Coles para resultados bajos."""
    ph = poisson.pmf(np.arange(maxg + 1), lh)
    pa = poisson.pmf(np.arange(maxg + 1), la)
    g = np.outer(ph, pa)
    r = _RHO
    g[0, 0] *= 1 - lh * la * r
    g[0, 1] *= 1 + lh * r
    g[1, 0] *= 1 + la * r
    g[1, 1] *= 1 - r
    g = np.clip(g, 1e-12, None)
    return g / g.sum()


def top_scores(lh, la, k=10, maxg=6):
    """Los k marcadores exactos más probables (Poisson + Dixon-Coles)."""
    g = _dc_grid(lh, la, maxg)
    cells = [((i, j), float(g[i, j])) for i in range(maxg + 1) for j in range(maxg + 1)]
    cells.sort(key=lambda c: c[1], reverse=True)
    return [{"score": [i, j], "p": round(p, 3)} for (i, j), p in cells[:k]]


def build_factors(engine, a, b):
    """Datos en que se basa la predicción (para el '¿por qué?')."""
    fa = engine.fb._form(a); fbf = engine.fb._form(b)
    return {
        "eloA": round(float(engine.elo.get(a, 1500))),
        "eloB": round(float(engine.elo.get(b, 1500))),
        "formA": round(float(fa[0]), 2), "formB": round(float(fbf[0]), 2),
        "xgA": engine.xg.get(a, (None,))[0] if a in engine.xg else None,
        "xgB": engine.xg.get(b, (None,))[0] if b in engine.xg else None,
        "market": (a, b) in engine.market,
    }


def timeline_from_score(sa, sb, timing, rng, et=False, fav_side=None):
    minsA = timing.sample_minutes(sa, rng)
    minsB = timing.sample_minutes(sb, rng)
    if et:
        extra = timing.sample_minutes(1, rng, extra_time=True)
        if fav_side == "A" and minsA:
            minsA[-1] = extra[0]
        elif fav_side == "B" and minsB:
            minsB[-1] = extra[0]
    ev = ([{"minute": m, "team": "A"} for m in minsA] +
          [{"minute": m, "team": "B"} for m in minsB])
    ev.sort(key=lambda e: e["minute"])
    ra = rb = 0; tl = []
    for e in ev:
        if e["team"] == "A":
            ra += 1
        else:
            rb += 1
        tl.append({"minute": e["minute"], "team": e["team"], "a": ra, "b": rb})
    return tl


def est_corners(lh, la):
    """Córners esperados (estimación desde la fuerza ofensiva; no dataset real)."""
    avg = 1.35  # gol esperado promedio
    ca = round(min(9.5, max(2.0, 5.0 * lh / avg)), 1)
    cb = round(min(9.5, max(2.0, 5.0 * la / avg)), 1)
    return {"a": ca, "b": cb}


def buckets(lmbda, timing):
    return {lbl: round(float(1 - np.exp(-lmbda * timing.bucket_probs[i])), 3)
            for i, lbl in enumerate(BUCKET_LABELS)}


def predict_group_match(engine, m, timing, rng):
    a, b, neutral = m["home"], m["away"], m["neutral"]
    proba = engine.outcome_blended(a, b, neutral)   # modelo + mercado (si hay cuotas)
    lh, la = engine.lambdas(a, b, neutral)
    sa, sb = most_likely_score(lh, la, outcome=int(proba.argmax()))
    mb = engine.outcome_by_model(a, b, neutral)
    mb["ens"] = [round(float(x), 4) for x in proba]  # ens del modal = producción (con mercado)
    return {
        "match": m.get("id"), "round": "group", "group": m["group"],
        "date": m["date"], "teamA": a, "teamB": b,
        "p1": round(float(proba[0]), 4), "px": round(float(proba[1]), 4),
        "p2": round(float(proba[2]), 4), "pred": LBL[int(proba.argmax())],
        "models": mb,
        "scoreA": sa, "scoreB": sb, "xgA": round(float(lh), 2),
        "xgB": round(float(la), 2),
        "timeline": timeline_from_score(sa, sb, timing, rng),
        "bucketsA": buckets(lh, timing), "bucketsB": buckets(la, timing),
        "cards": engine.cards.expected(a, b, knockout=False),
        "corners": est_corners(lh, la),
        "hasOdds": (a, b) in engine.market,
        "topScores": top_scores(lh, la),
        "factors": build_factors(engine, a, b),
        "penShareA": engine.pen_share.get(a), "penShareB": engine.pen_share.get(b),
        "scorersA": engine.scorers.get(a), "scorersB": engine.scorers.get(b),
        "injuriesA": engine.injuries.get(a, []), "injuriesB": engine.injuries.get(b, []),
        "moraleA": engine.morale.get(a), "moraleB": engine.morale.get(b),
    }


def predict_ko_match(engine, a, b, timing, rng, n=N_MATCH, model="ens"):
    lh, la = engine.lambdas(a, b, True)
    res = {"regular": 0, "ET": 0, "pens": 0}
    pen_total = 0; pen_a = 0
    for _ in range(n):
        w, gh, ga, decided = engine.sim_ko_match(a, b, rng)
        res[decided] += 1
        if decided == "pens":
            pen_total += 1
            if w == a:
                pen_a += 1
    # Quién avanza según el MODELO elegido: P(A avanza) = P(gana A) + P(empate)·P(A en penales)
    mb = engine.outcome_by_model(a, b, True)
    p1, px, p2 = mb[model]
    pp = engine.pen_prob(a, b)
    adv_a = p1 + px * pp
    adv_b = p2 + px * (1 - pp)
    pA = adv_a / (adv_a + adv_b) if (adv_a + adv_b) else 0.5
    favorite = a if pA >= 0.5 else b
    # Marcador representativo DETERMINISTA: el más probable donde gana el favorito
    # (coherente con el top-5 y sin ruido de simulación).
    fav_outcome = 0 if favorite == a else 2
    scoreA, scoreB = most_likely_score(lh, la, outcome=fav_outcome)
    decided = "regular"
    fav_side = "A" if favorite == a else "B"
    penA = penB = None
    # prob. de ganar en penales (si se llega a penales)
    pen_win_a = round(pen_a / pen_total, 3) if pen_total else round(engine.pen_prob(a, b), 3)
    return {
        "teamA": a, "teamB": b, "pA": round(pA, 4), "pB": round(1 - pA, 4),
        "models": mb,
        "winner": favorite, "scoreA": int(scoreA), "scoreB": int(scoreB),
        "decided": decided, "penA": penA, "penB": penB,
        "xgA": round(float(lh), 2), "xgB": round(float(la), 2),
        "timeline": timeline_from_score(scoreA, scoreB, timing, rng,
                                        et=decided == "ET", fav_side=fav_side),
        "bucketsA": buckets(lh, timing), "bucketsB": buckets(la, timing),
        "cards": engine.cards.expected(a, b, knockout=True),
        "corners": est_corners(lh, la),
        "topScores": top_scores(lh, la),
        "factors": build_factors(engine, a, b),
        "resolution": {k: round(v / n, 3) for k, v in res.items()},
        "penWinA": pen_win_a, "penWinB": round(1 - pen_win_a, 3),
        "penShareA": engine.pen_share.get(a), "penShareB": engine.pen_share.get(b),
        "scorersA": engine.scorers.get(a), "scorersB": engine.scorers.get(b),
        "injuriesA": engine.injuries.get(a, []), "injuriesB": engine.injuries.get(b, []),
        "moraleA": engine.morale.get(a), "moraleB": engine.morale.get(b),
    }


def predicted_bracket(engine, r32_teams, timing, seed=7, model="ens"):
    rng = np.random.default_rng(seed)
    br = {"R32": [], "R16": [], "QF": [], "SF": [], "Final": [], "third": []}
    winners = {}
    for mid in sorted(R32_STRUCTURE):
        a, b = r32_teams[mid]
        p = predict_ko_match(engine, a, b, timing, rng, model=model)
        p["match"] = mid; p["round"] = "R32"; br["R32"].append(p)
        winners[mid] = p["winner"]
    for feed, name in ((R16_FEED, "R16"), (QF_FEED, "QF"),
                       (SF_FEED, "SF"), (FINAL_FEED, "Final")):
        for mid in sorted(feed):
            fa, fb = feed[mid]
            p = predict_ko_match(engine, winners[fa], winners[fb], timing, rng, model=model)
            p["match"] = mid; p["round"] = name; br[name].append(p)
            winners[mid] = p["winner"]
    sf = {p["match"]: p for p in br["SF"]}
    losers = [(p["teamB"] if p["winner"] == p["teamA"] else p["teamA"])
              for p in sf.values()]
    if len(losers) == 2:
        p = predict_ko_match(engine, losers[0], losers[1], timing, rng, model=model)
        p["match"] = 103; p["round"] = "third"; br["third"].append(p)
    champ = br["Final"][0]["winner"] if br["Final"] else None
    return br, champ


def r32_for_model(group_preds, played_df, groups, model):
    """Clasificados a 16vos según las predicciones de grupo del MODELO elegido."""
    pred_rows = []
    for gp in group_preds:
        o = int(np.argmax(gp["models"][model]))
        sa, sb = most_likely_score(gp["xgA"], gp["xgB"], outcome=o)
        pred_rows.append({"home_team": gp["teamA"], "away_team": gp["teamB"],
                          "home_score": sa, "away_score": sb})
    combined = pd.concat([
        played_df[["home_team", "away_team", "home_score", "away_score"]],
        pd.DataFrame(pred_rows)], ignore_index=True)
    fs = compute_standings(combined, groups)
    return resolve_r32_teams(qualifiers(fs))


# ------------------------- standings para mostrar -------------------------
def display_standings(all_results_df, groups):
    """Tabla actual usando partidos jugados (criterios FIFA, con H2H)."""
    return compute_standings(all_results_df, groups)


def main():
    print("Cargando datos y entrenando modelo...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    timing = GoalTimingModel().fit()
    # Ajustar rho de Dixon-Coles con datos reales (marcadores más precisos)
    global _RHO
    try:
        from statmodel import StatModel
        samp = feats.tail(4000)
        _RHO = StatModel(gm).fit_rho(samp["lam_h"].to_numpy(),
                                     samp["lam_a"].to_numpy(),
                                     samp["label"].to_numpy().astype(int))
        print(f"  Dixon-Coles rho ajustado: {_RHO:.3f}")
    except Exception as e:  # noqa: BLE001
        print("  (rho por defecto:", e, ")")
    engine = Engine(fb, model, elo, timing)

    # Modelos individuales (para el selector en la web): Elo y Estadístico
    try:
        from elomodel import EloModel
        from statmodel import StatModel
        lab = np.where(results["home_score"].to_numpy() > results["away_score"].to_numpy(), 0,
                       np.where(results["home_score"].to_numpy() < results["away_score"].to_numpy(), 2, 1))
        engine.elom = EloModel().fit(results["home_elo"].to_numpy(), results["away_elo"].to_numpy(),
                                     results["neutral"].to_numpy(), lab)
        engine.statm = StatModel(gm, rho=_RHO)
        print("  Modelos individuales (Elo + Estadístico) listos para el selector.")
    except Exception as e:  # noqa: BLE001
        print("  (selector de modelos no disponible:", e, ")")

    groups = load_official_groups()
    fixtures = get_wc2026_fixtures()
    played_df = fixtures[fixtures["played"]].copy()
    played_df["home_score"] = played_df["home_score"].astype(int)
    played_df["away_score"] = played_df["away_score"].astype(int)
    remaining = [
        {"home": r.home_team, "away": r.away_team, "neutral": bool(r.neutral),
         "date": str(r.date.date()), "id": 1000 + i,
         "group": next(g for g, ts in groups.items() if r.home_team in ts)}
        for i, r in enumerate(fixtures[~fixtures["played"]].itertuples(index=False))
    ]
    print(f"Grupos: {len(played_df)} partidos jugados, "
          f"{len(remaining)} por jugar.")

    # --- predicciones de los partidos de grupo restantes ---
    rng0 = np.random.default_rng(11)
    group_preds = [predict_group_match(engine, m, timing, rng0) for m in remaining]

    # --- completar grupos de forma determinista (marcador más probable) ---
    pred_rows = []
    for gp in group_preds:
        pred_rows.append({"home_team": gp["teamA"], "away_team": gp["teamB"],
                          "home_score": gp["scoreA"], "away_score": gp["scoreB"]})
    combined = pd.concat([
        played_df[["home_team", "away_team", "home_score", "away_score"]],
        pd.DataFrame(pred_rows)], ignore_index=True)
    final_standings = compute_standings(combined, groups)
    qual = qualifiers(final_standings)
    r32_teams, third_assign = resolve_r32_teams(qual)

    # --- Un cuadro por CADA modelo (para el selector en la pantalla de eliminatorias) ---
    print(f"Simulando el cuadro con cada modelo ({N_MATCH} sims/partido)...")
    brackets = {}; champions = {}
    for mk in ("ens", "xgb", "stat", "elo"):
        r32_m, _ = r32_for_model(group_preds, played_df, groups, mk)
        brackets[mk], champions[mk] = predicted_bracket(engine, r32_m, timing, model=mk)
        print(f"  {mk}: campeón {champions[mk]}")
    bracket, champion = brackets["ens"], champions["ens"]

    print(f"Monte Carlo desde el estado actual ({N_SIMS} torneos)...")
    base_stats, _ = base_group_stats(played_df, groups)
    adv = monte_carlo(engine, base_stats, groups, remaining)

    team_group = {t: g for g, ts in groups.items() for t in ts}
    adv_list = [{"team": t, "group": team_group.get(t, "?"),
                 "elo": round(float(elo.get(t, 1500)), 1), **p}
                for t, p in adv.items()]

    # Prior de mercado: cuotas de campeón -> columna "market" + blend 50/50
    champ_odds = _load_champion_odds()
    if champ_odds:
        for r in adv_list:
            r["market_champ"] = champ_odds.get(r["team"])
        blended = {}
        for r in adv_list:
            mk = r.get("market_champ")
            blended[r["team"]] = (0.5 * r["Champion"] + 0.5 * mk) if mk is not None else r["Champion"]
        s = sum(blended.values()) or 1.0
        for r in adv_list:
            r["champ_blend"] = round(blended[r["team"]] / s, 4)

    adv_list.sort(key=lambda r: (r.get("champ_blend", r["Champion"]), r["Final"],
                                 r["SF"], r["Qualify"]), reverse=True)

    # standings actuales (reales) + nº de partidos jugados por grupo
    cur_standings = display_standings(
        played_df[["home_team", "away_team", "home_score", "away_score"]], groups)
    group_complete = {g: all(row["P"] == 3 for row in cur_standings[g])
                      for g in groups}

    payload = {
        "meta": {
            "title": "Predicción Mundial 2026 — XGBoost + Ratings",
            "data_through": str(results["date"].max().date()),
            "n_sims": N_SIMS, "n_match_sims": N_MATCH,
            "model_metrics": model.metrics, "champion_pick": champion,
            "matches_played": int(len(played_df)),
            "matches_remaining_group": int(len(remaining)),
        },
        "groups": {g: [_clean(r) for r in cur_standings[g]] for g in cur_standings},
        "group_complete": group_complete,
        "group_predictions": group_preds,
        "third_assignment": {str(k): v for k, v in third_assign.items()},
        "elo": {t: round(float(elo.get(t, 1500)), 1) for t in team_group},
        "bracket": bracket,
        "brackets": brackets,        # un cuadro por modelo (ens/xgb/stat/elo)
        "champions": champions,      # campeón previsto por modelo
        "advancement": adv_list,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nOK -> {OUT_PATH}")
    print(f"Campeón previsto: {champion}")
    print("Top 8 (prob. de campeón):")
    for r in adv_list[:8]:
        print(f"  {r['team']:<20} {r['Champion']*100:5.1f}%  "
              f"(clasifica {r['Qualify']*100:4.0f}%, Final {r['Final']*100:4.1f}%)")


def _clean(r):
    return {k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in r.items()}


if __name__ == "__main__":
    main()
