"""Predicción de las eliminatorias sobre el cuadro REAL de la Ronda de 32.

Toma los 16 cruces reales (cuadro oficial) y predice octavos -> final con el
modelo (XGBoost + ratings), más un Monte Carlo para las probabilidades de título.
"""
from __future__ import annotations

from collections import defaultdict
import numpy as np

from data_prep import load_results
from ratings import compute_elo, GoalsModel
from goal_timing import GoalTimingModel
from model import FeatureBuilder, WCModel
from simulate import Engine, predict_ko_match

# Cuadro REAL (orden del bracket: cada par consecutivo alimenta unos octavos)
R32_REAL = [
    ("Germany", "Paraguay"), ("France", "Sweden"),
    ("South Korea", "Switzerland"), ("Netherlands", "Morocco"),
    ("Portugal", "Ghana"), ("Spain", "Austria"),
    ("United States", "Algeria"), ("Egypt", "Czech Republic"),
    ("Brazil", "Japan"), ("Ivory Coast", "Norway"),
    ("Mexico", "Scotland"), ("England", "Cape Verde"),
    ("Argentina", "Uruguay"), ("Australia", "Iran"),
    ("Canada", "Belgium"), ("Colombia", "Croatia"),
]
ES = {"Germany": "Alemania", "Paraguay": "Paraguay", "France": "Francia",
      "Sweden": "Suecia", "South Korea": "Corea del Sur", "Switzerland": "Suiza",
      "Netherlands": "Países Bajos", "Morocco": "Marruecos", "Portugal": "Portugal",
      "Ghana": "Ghana", "Spain": "España", "Austria": "Austria",
      "United States": "Estados Unidos", "Algeria": "Argelia", "Egypt": "Egipto",
      "Czech Republic": "Chequia", "Brazil": "Brasil", "Japan": "Japón",
      "Ivory Coast": "Costa de Marfil", "Norway": "Noruega", "Mexico": "México",
      "Scotland": "Escocia", "England": "Inglaterra", "Cape Verde": "Cabo Verde",
      "Argentina": "Argentina", "Uruguay": "Uruguay", "Australia": "Australia",
      "Iran": "Irán", "Canada": "Canadá", "Belgium": "Bélgica",
      "Colombia": "Colombia", "Croatia": "Croacia"}
def n(t): return ES.get(t, t)


def setup_engine():
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    timing = GoalTimingModel().fit()
    return Engine(fb, model, elo, timing), elo


def champion_montecarlo(engine, n_sims=20000, seed=1):
    rng = np.random.default_rng(seed)
    champ = defaultdict(int); finals = defaultdict(int); semis = defaultdict(int)
    for _ in range(n_sims):
        r32w = [engine.sim_ko_match(a, b, rng)[0] for a, b in R32_REAL]   # 16
        octv = [engine.sim_ko_match(r32w[i], r32w[i + 1], rng)[0]
                for i in range(0, 16, 2)]                                 # 8
        qf = [engine.sim_ko_match(octv[i], octv[i + 1], rng)[0]
              for i in range(0, 8, 2)]                                    # 4 (semifinalistas)
        for t in qf:
            semis[t] += 1
        sf = [engine.sim_ko_match(qf[i], qf[i + 1], rng)[0]
              for i in range(0, 4, 2)]                                    # 2 (finalistas)
        for t in sf:
            finals[t] += 1
        champ[engine.sim_ko_match(sf[0], sf[1], rng)[0]] += 1
    return champ, finals, semis, n_sims


def main():
    print("Entrenando modelo...")
    engine, elo = setup_engine()
    rng = np.random.default_rng(7)

    print("\n=== RONDA DE 32 / 16avos (predicción sobre el cuadro REAL) ===")
    r32_winners = []
    for a, b in R32_REAL:
        p = predict_ko_match(engine, a, b, engine.timing, rng)
        r32_winners.append(p["winner"])
        print(f"  {n(a):>16} {p['pA']*100:4.1f}% - {p['pB']*100:4.1f}% {n(b):<16}"
              f" -> {n(p['winner'])} {p['scoreA']}-{p['scoreB']}")

    def round_pred(ws, label):
        print(f"\n=== {label} ===")
        nxt = []
        for i in range(0, len(ws), 2):
            p = predict_ko_match(engine, ws[i], ws[i + 1], engine.timing, rng)
            nxt.append(p["winner"])
            print(f"  {n(ws[i]):>16} {p['pA']*100:4.1f}% - {p['pB']*100:4.1f}%"
                  f" {n(ws[i+1]):<16} -> {n(p['winner'])} {p['scoreA']}-{p['scoreB']}")
        return nxt

    octv = round_pred(r32_winners, "OCTAVOS")
    qf = round_pred(octv, "CUARTOS")
    sf = round_pred(qf, "SEMIFINALES")
    fin = round_pred(sf, "FINAL")
    print(f"\n  >>> CAMPEÓN PREVISTO: {n(fin[0])} <<<")

    print("\nMonte Carlo (20.000) sobre el cuadro real...")
    champ, finals, semis, N = champion_montecarlo(engine)
    ranked = sorted(champ.items(), key=lambda kv: kv[1], reverse=True)
    print("\n=== TOP 10 — prob. de campeón (cuadro REAL) ===")
    for i, (t, c) in enumerate(ranked[:10], 1):
        print(f"  {i:2}. {n(t):<16} campeón {c/N*100:5.1f}%  "
              f"| final {finals[t]/N*100:4.1f}% | semis {semis[t]/N*100:4.1f}%")


if __name__ == "__main__":
    main()
