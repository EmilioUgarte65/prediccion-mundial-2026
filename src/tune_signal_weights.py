"""Tunea el PESO de cada señal forward contra el torneo real 2026.

Descenso de coordenadas: para cada señal prueba una rejilla de pesos (las demás
fijas), elige el que minimiza el error de goles (MAE) contra los partidos jugados,
e itera. Así una señal que "estorbaba" a peso 1.0 encuentra su peso útil.

CAVEAT: se ajusta sobre ~60 partidos -> hay riesgo de sobreajuste. Por eso la
rejilla es gruesa y se prefieren pesos moderados ante empates.
"""
from __future__ import annotations

from simulate import (Engine, most_likely_score, load_results, compute_elo,
                      GoalsModel, FeatureBuilder, WCModel, GoalTimingModel,
                      get_wc2026_fixtures)

GRID = {
    "xg": [0, 0.2, 0.35, 0.5, 0.7],
    "inj": [0, 0.25, 0.5, 0.75, 1.0],
    "morale": [0, 0.5, 1.0, 1.5, 2.0],
    "fatigue": [0, 0.25, 0.5, 0.75, 1.0],
    "patt": [0, 0.5, 1.0, 1.5],
    "avail": [0, 0.5, 1.0, 1.5],
    "weather": [0, 0.5, 1.0],
}


def main():
    print("Entrenando motor...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    timing = GoalTimingModel().fit()
    engine = Engine(fb, model, elo, timing)

    played = get_wc2026_fixtures()
    played = played[played["played"]].copy()
    n = len(played)
    games = [(r.home_team, r.away_team, bool(r.neutral),
              int(r.home_score), int(r.away_score))
             for r in played.itertuples(index=False)]
    print(f"Ajustando pesos contra {n} partidos reales...\n")

    def score():
        engine.lam_cache.clear()
        mae = exact = 0
        for h, a, neu, rh, ra in games:
            lh, la = engine.lambdas(h, a, neu)
            sh, sa = most_likely_score(lh, la)
            mae += abs(sh - rh) + abs(sa - ra)
            exact += int(sh == rh and sa == ra)
        return mae / (2 * n), exact / n

    base_mae, base_ex = score()
    print(f"Pesos iniciales {engine.W}")
    print(f"  MAE {base_mae:.3f} · exacto {base_ex*100:.1f}%\n")

    for it in range(2):
        for sig, grid in GRID.items():
            best_w, best = engine.W[sig], score()[0]
            for w in grid:
                engine.W[sig] = w
                mae = score()[0]
                # preferir peso menor ante mejora despreciable (regularización)
                if mae < best - 0.0005 or (abs(mae - best) <= 0.0005 and w < best_w):
                    best, best_w = mae, w
            engine.W[sig] = best_w
        print(f"Pasada {it+1}: {{" + ", ".join(f'{k}:{v}' for k, v in engine.W.items()) + "}")

    fin_mae, fin_ex = score()
    print(f"\n=== PESOS ÓPTIMOS (vs torneo real) ===")
    for k, v in engine.W.items():
        print(f"  {k:<9} {v}")
    print(f"\nMAE {base_mae:.3f} -> {fin_mae:.3f} | exacto {base_ex*100:.1f}% -> {fin_ex*100:.1f}%")
    print("\nCopia este dict a Engine.W en simulate.py:")
    print("    W =", {k: v for k, v in engine.W.items()})


if __name__ == "__main__":
    main()
