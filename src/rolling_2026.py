"""Walk-forward rodante del Mundial 2026 con el ensemble óptimo.

Lee backtest.json (probabilidades punto-en-el-tiempo de cada modelo) y, en orden
cronológico, predice cada partido ANTES de jugarse y muestra el acierto que se va
acumulando a medida que entran los resultados (el Elo/forma ya se actualizan en
cada paso porque las features son pre-partido).

Pesos del ensemble: los óptimos hallados en 1998-2014 (Elo 0.7, XGBoost 0.3).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
W_ELO, W_STAT, W_XGB = 0.7, 0.0, 0.3
LAB = {0: "1", 1: "X", 2: "2"}
ES = {"Czech Republic": "Chequia", "South Africa": "Sudafrica", "South Korea": "Corea S.",
      "United States": "EE.UU.", "Ivory Coast": "C.Marfil", "Cape Verde": "C.Verde",
      "Saudi Arabia": "Arabia S.", "Netherlands": "P.Bajos", "New Zealand": "N.Zelanda",
      "Bosnia and Herzegovina": "Bosnia", "DR Congo": "RD Congo"}


def n(t):
    return ES.get(t, t)


def main():
    bt = json.load(open(os.path.join(ROOT, "web", "data", "backtest.json"), encoding="utf-8"))
    matches = [m for m in bt["matches"] if m.get("eligible")]
    matches.sort(key=lambda m: m["date"])

    print(f"WALK-FORWARD RODANTE — Mundial 2026 (ensemble Elo {W_ELO} + XGB {W_XGB})")
    print(f"{'Fecha':<11}{'Partido':<30}{'Pred':>5}{'Prob':>6}{'Real':>6}{'OK':>4}{'Acum.':>8}")
    print("-" * 70)
    hit = tot = 0
    for m in matches:
        pe = [m["el1"], m["elx"], m["el2"]]
        ps = [m["s1"], m["sx"], m["s2"]]
        px = [m["p1"], m["px"], m["p2"]]
        P = [W_ELO * pe[i] + W_STAT * ps[i] + W_XGB * px[i] for i in range(3)]
        k = max(range(3), key=lambda i: P[i])
        pred = LAB[k]
        real = m["real"]
        ok = pred == real
        tot += 1; hit += int(ok)
        part = f"{n(m['home'])} v {n(m['away'])}"
        print(f"{m['date']:<11}{part:<30}{pred:>5}{P[k]*100:5.0f}%"
              f"{(str(m['real_score'][0])+'-'+str(m['real_score'][1])):>6}"
              f"{('OK' if ok else 'x'):>4}{f'{hit}/{tot}':>8}")
    print("-" * 70)
    print(f"ACIERTO FINAL: {hit}/{tot} = {hit/tot*100:.1f}%")


if __name__ == "__main__":
    main()
