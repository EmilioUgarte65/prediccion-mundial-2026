"""Ablación de señales forward contra el torneo REAL 2026.

Para cada señal (lesiones, ánimo, fatiga, bottom-up, defensa, disponibilidad,
clima, xG, cuotas) mide si QUITARLA empeora o mejora la predicción de los
partidos ya jugados. Si al quitarla empeora -> la señal AYUDA.

CAVEAT honesto: el bottom-up mezcla goles reales del torneo (fuga parcial para
partidos jugados) y lesiones/ánimo/disponibilidad son foto actual (no exactamente
pre-partido). Aun así es la mejor medición posible con datos reales.
"""
from __future__ import annotations

from simulate import (Engine, most_likely_score, load_results, compute_elo,
                      GoalsModel, FeatureBuilder, WCModel, GoalTimingModel,
                      get_wc2026_fixtures)


def main():
    print("Entrenando motor completo...")
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
    print(f"Partidos reales para validar: {n}\n")

    # señales que viven en atributos-dict del motor (toggle = vaciar)
    SIGNALS = {
        "xG externo": "xg", "lesiones": "injuries", "ánimo (PNL)": "morale",
        "fatiga": "fatigue", "bottom-up+defensa": "patt",
        "disponibilidad": "avail", "clima": "weather", "cuotas (mercado)": "market",
    }

    def evaluate(disable=()):
        saved = {}
        for attr in disable:
            saved[attr] = getattr(engine, attr, None)
            setattr(engine, attr, {})
        engine.lam_cache.clear()
        mae = exact = winner = 0
        for r in played.itertuples(index=False):
            lh, la = engine.lambdas(r.home_team, r.away_team, bool(r.neutral))
            sh, sa = most_likely_score(lh, la)
            rh, ra = int(r.home_score), int(r.away_score)
            mae += abs(sh - rh) + abs(sa - ra)
            exact += int(sh == rh and sa == ra)
            pw = (sh > sa) - (sh < sa); rw = (rh > ra) - (rh < ra)
            winner += int(pw == rw)
        for attr, v in saved.items():
            setattr(engine, attr, v)
        engine.lam_cache.clear()
        return mae / (2 * n), exact / n * 100, winner / n * 100

    base = evaluate()
    print(f"{'Config':<22}{'MAE goles':>10}{'Exacto':>9}{'Ganador':>9}{'ΔMAE':>9}")
    print(f"{'COMPLETO (todo)':<22}{base[0]:>10.3f}{base[1]:>8.1f}%{base[2]:>8.1f}%{'—':>9}")
    print("-" * 60)
    rows = []
    for name, attr in SIGNALS.items():
        r = evaluate(disable=[attr])
        d = r[0] - base[0]  # >0 = al quitarla empeora (la señal ayuda)
        verdict = "ayuda" if d > 0.003 else ("estorba" if d < -0.003 else "neutra")
        rows.append((name, d, verdict))
        print(f"{'sin ' + name:<22}{r[0]:>10.3f}{r[1]:>8.1f}%{r[2]:>8.1f}%{d:>+9.3f}  {verdict}")

    print("\n=== Resumen ===")
    helps = [n for n, d, v in rows if v == "ayuda"]
    neut = [n for n, d, v in rows if v == "neutra"]
    hurts = [n for n, d, v in rows if v == "estorba"]
    print("AYUDAN:", ", ".join(helps) or "ninguna")
    print("NEUTRAS:", ", ".join(neut) or "ninguna")
    print("ESTORBAN:", ", ".join(hurts) or "ninguna")


if __name__ == "__main__":
    main()
