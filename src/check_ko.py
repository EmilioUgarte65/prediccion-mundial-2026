"""Valida frecuencia de prórroga/penales y el sesgo del favorito en penales."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from collections import Counter

from data_prep import load_results
from ratings import compute_elo, GoalsModel
from goal_timing import GoalTimingModel
from model import FeatureBuilder, WCModel
from simulate import Engine


def main():
    print("Entrenando modelo para el chequeo...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    eng = Engine(fb, model, elo, GoalTimingModel().fit())

    # 32 clasificados aprox (usar top equipos por Elo como muestra)
    teams = [t for t, _ in sorted(elo.items(), key=lambda kv: kv[1], reverse=True)[:32]]
    rng = np.random.default_rng(0)
    dec = Counter(); pen_fav_win = 0; pen_n = 0; N = 20000
    for _ in range(N):
        a, b = rng.choice(teams, 2, replace=False)
        w, gh, ga, d = eng.sim_ko_match(a, b, rng)
        dec[d] += 1
        if d == "pens":
            pen_n += 1
            fav = a if elo[a] >= elo[b] else b
            if w == fav:
                pen_fav_win += 1
    print(f"\nDe {N} partidos de eliminatoria simulados:")
    for k in ("regular", "ET", "pens"):
        print(f"  {k:>8}: {dec[k]/N*100:5.1f}%")
    print(f"\nEn penales, gana el FAVORITO: {pen_fav_win/pen_n*100:.1f}%  "
          f"(real ~53-57%)")
    print("Referencia real Mundiales: ~20-26% van a prórroga, ~10-14% a penales.")


if __name__ == "__main__":
    main()
