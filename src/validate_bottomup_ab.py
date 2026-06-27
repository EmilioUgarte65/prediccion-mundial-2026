"""A/B test del modelo bottom-up (jugadores) en los partidos de grupo ya jugados.

Predice el marcador de cada partido jugado CON y SIN el ajuste bottom-up y compara
el error de goles y el acierto de marcador exacto contra la realidad. El resto del
motor es idéntico en ambos brazos, así que la diferencia aísla el efecto del modelo.
"""
from __future__ import annotations

import simulate as S
from simulate import (Engine, most_likely_score, load_results, compute_elo,
                      GoalsModel, FeatureBuilder, WCModel, GoalTimingModel,
                      get_wc2026_fixtures)


def main():
    print("Entrenando motor (igual que en producción)...")
    results = load_results()
    results, elo = compute_elo(results)
    gm = GoalsModel().fit(results)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    model = WCModel().train(feats)
    timing = GoalTimingModel().fit()
    engine = Engine(fb, model, elo, timing)

    fixtures = get_wc2026_fixtures()
    played = fixtures[fixtures["played"]].copy()
    print(f"Partidos jugados para el A/B: {len(played)}\n")

    def evaluate(use_patt):
        saved = engine.patt
        engine.patt = saved if use_patt else {}
        mae = exact = winner = n = 0
        for r in played.itertuples(index=False):
            lh, la = engine.lambdas(r.home_team, r.away_team, neutral=bool(r.neutral))
            sh, sa = most_likely_score(lh, la)
            rh, ra = int(r.home_score), int(r.away_score)
            mae += abs(sh - rh) + abs(sa - ra)
            exact += int(sh == rh and sa == ra)
            # ganador segun el marcador previsto
            pw = (sh > sa) - (sh < sa); rw = (rh > ra) - (rh < ra)
            winner += int(pw == rw)
            n += 1
        engine.patt = saved
        return mae / (2 * n), exact / n, winner / n

    rows = {}
    for use in (True, False):
        rows["CON" if use else "SIN"] = evaluate(use)

    print(f"{'Brazo':>6}{'MAE/equipo':>13}{'Exacto':>10}{'Ganador (marcador)':>22}")
    for k in ("CON", "SIN"):
        mae, ex, wn = rows[k]
        print(f"{k:>6}{mae:>12.3f}{ex*100:>9.1f}%{wn*100:>20.1f}%")
    dmae = rows["SIN"][0] - rows["CON"][0]
    print(f"\nMejora del bottom-up en MAE de goles: {dmae:+.3f} por equipo "
          f"({'mejora' if dmae > 0 else 'empeora' if dmae < 0 else 'neutro'})")


if __name__ == "__main__":
    main()
