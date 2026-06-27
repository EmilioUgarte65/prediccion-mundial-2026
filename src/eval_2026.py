"""Chequeo de aciertos del modelo en los partidos de 2026 ya jugados.

Clasifica cada predicción (hecha ANTES del partido, walk-forward) en:
- BIEN: acertó quién ganó (1-X-2).
- MÁS O MENOS: falló el 1-X-2 pero era partido parejo (el modelo no estaba
  seguro, <50%) o era un empate (casi imposible de clavar).
- MAL: el modelo estaba seguro (>=50%) y salió lo contrario.
Además cuenta los marcadores EXACTOS clavados.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(__file__))
LAB = {"1": 0, "X": 1, "2": 2}


def main():
    bt = json.load(open(os.path.join(ROOT, "web", "data", "backtest.json"),
                       encoding="utf-8"))
    ms = bt["matches"]
    bien = reg = mal = exacto = 0
    detalle = {"bien": [], "regular": [], "mal": []}
    for m in ms:
        P = {"1": m["p1"], "X": m["px"], "2": m["p2"]}
        conf = max(P.values())
        ok = m["pred"] == m["real"]
        if m["pred_score"] == m["real_score"]:
            exacto += 1
        if ok:
            bien += 1
            detalle["bien"].append(m)
        elif conf < 0.50 or m["real"] == "X":
            reg += 1
            detalle["regular"].append(m)
        else:
            mal += 1
            detalle["mal"].append(m)
    n = len(ms)
    print(f"=== CHEQUEO 2026 ({n} partidos jugados) ===")
    print(f"  ✅ BIEN (acertó ganador):      {bien}  ({bien/n*100:.0f}%)")
    print(f"  🟡 MÁS O MENOS (parejo/empate): {reg}  ({reg/n*100:.0f}%)")
    print(f"  ❌ MAL (seguro y falló):        {mal}  ({mal/n*100:.0f}%)")
    print(f"  🎯 Marcador EXACTO clavado:     {exacto}  ({exacto/n*100:.0f}%)")
    print(f"\n  -> De los que NO acertó, {reg}/{reg+mal} eran parejos/empates "
          f"(errores 'razonables') y solo {mal} fueron errores claros.")
    print("\nErrores claros (MAL):")
    for m in detalle["mal"]:
        print(f"  {m['home']} {m['real_score'][0]}-{m['real_score'][1]} {m['away']} "
              f"(predije {m['pred']} con {max(m['p1'],m['px'],m['p2'])*100:.0f}%)")


if __name__ == "__main__":
    main()
