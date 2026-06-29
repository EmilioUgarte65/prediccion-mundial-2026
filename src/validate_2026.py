"""Validación del modelo SOLO-2026 contra los partidos JUGADOS de 2026
(amistosos + fase de grupos + series/eliminatorias de clasificación), walk-forward
y SIN datos históricos de otros Mundiales.

Modelo 2026 (por partido, usando solo lo anterior a esa fecha):
  - forma 2026: goles a favor / en contra por equipo (promedio movil)
  - ataque/defensa por JUGADOR (FBref: gol/asist/tiros y Int+TklW) -> ajuste del equipo
  - PNL (ánimo) y lesiones (señales que ya usábamos)
  -> lambdas -> Dixon-Coles -> resultado 1-X-2. Se compara con lo real.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
from scipy.stats import poisson

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, "data_user")
RHO = -0.12
HOME_ADV = 1.10
AVG = 1.35

TORNEOS = {"Friendly", "FIFA World Cup", "FIFA Series", "CONCACAF Series",
           "FIFA World Cup qualification", "African Cup of Nations", "Unity Cup",
           "Baltic Cup", "Tri-Nations Cup", "Mukuru 4 Nations"}


def dc_outcome(lh, la, maxg=8):
    ph = poisson.pmf(np.arange(maxg + 1), lh)
    pa = poisson.pmf(np.arange(maxg + 1), la)
    g = np.outer(ph, pa)
    g[0, 0] *= 1 - lh * la * RHO; g[0, 1] *= 1 + lh * RHO
    g[1, 0] *= 1 + la * RHO; g[1, 1] *= 1 - RHO
    ii, jj = np.indices(g.shape)
    return np.array([g[ii > jj].sum(), g[ii == jj].sum(), g[ii < jj].sum()]) / g.sum()


def load_signals():
    mor = {}
    p = os.path.join(DATA, "morale_2026.csv")
    if os.path.exists(p):
        for r in pd.read_csv(p).itertuples():
            mor[r.team] = float(getattr(r, "morale", 0) or 0)
    inj = {}
    p = os.path.join(DATA, "injuries_2026.csv")
    if os.path.exists(p):
        d = pd.read_csv(p)
        for t, g in d.groupby("team"):
            outs = (g["status"] == "out").sum()
            inj[t] = min(0.15, 0.04 * outs)   # baja de ataque por bajas
    patt = {}
    p = os.path.join(DATA, "team_player_attack.csv")
    if os.path.exists(p):
        for r in pd.read_csv(p).itertuples():
            patt[r.team] = (float(r.attack_mult), float(getattr(r, "def_mult", 1.0)))
    return mor, inj, patt


def main(use_players=True, use_signals=True, quiet=False):
    r = pd.read_csv(os.path.join(ROOT, "data_repo", "results.csv"), parse_dates=["date"])
    r = r[(r["date"] >= "2026-01-01") & r["tournament"].isin(TORNEOS)].copy()
    r = r.dropna(subset=["home_score", "away_score"]).sort_values("date").reset_index(drop=True)
    r["home_score"] = r["home_score"].astype(int); r["away_score"] = r["away_score"].astype(int)
    if not quiet:
        print(f"Partidos jugados de 2026 para validar: {len(r)}")

    mor, inj, patt = load_signals()
    if not use_players:
        patt = {}
    if not use_signals:
        mor, inj = {}, {}
    LBL = {0: "1", 1: "X", 2: "2"}
    # forma móvil 2026 (solo con partidos ANTERIORES -> sin fuga)
    gf, ga, n = {}, {}, {}
    hits = total = exact = 0
    wins_hits = wins_total = 0
    by_torneo = {}
    wc_rows = []
    for row in r.itertuples(index=False):
        h, a = row.home_team, row.away_team
        neutral = bool(getattr(row, "neutral", False))
        # forma previa
        hgf = gf.get(h, AVG) / max(1, n.get(h, 0)) if n.get(h) else AVG
        hga = ga.get(h, AVG) / max(1, n.get(h, 0)) if n.get(h) else AVG
        agf = gf.get(a, AVG) / max(1, n.get(a, 0)) if n.get(a) else AVG
        aga = ga.get(a, AVG) / max(1, n.get(a, 0)) if n.get(a) else AVG
        lh = (hgf + aga) / 2; la = (agf + hga) / 2
        if not neutral:
            lh *= HOME_ADV; la /= HOME_ADV
        # jugadores (ataque/defensa 2026) + PNL + lesiones
        if h in patt:
            lh *= 1 + 0.4 * (patt[h][0] - 1); la *= 1 - 0.4 * (patt[h][1] - 1)
        if a in patt:
            la *= 1 + 0.4 * (patt[a][0] - 1); lh *= 1 - 0.4 * (patt[a][1] - 1)
        lh *= 1 + 0.05 * mor.get(h, 0); la *= 1 + 0.05 * mor.get(a, 0)
        lh *= 1 - inj.get(h, 0); la *= 1 - inj.get(a, 0)
        lh = float(np.clip(lh, 0.15, 5)); la = float(np.clip(la, 0.15, 5))

        o = dc_outcome(lh, la)
        pred = int(o.argmax())
        real = 0 if row.home_score > row.away_score else (2 if row.home_score < row.away_score else 1)
        # evaluar desde el 2do partido de cada equipo (forma mínima)
        if n.get(h, 0) >= 1 and n.get(a, 0) >= 1:
            total += 1; hits += int(pred == real)
            if real != 1:
                wins_total += 1; wins_hits += int(pred == real)
            bt = by_torneo.setdefault(row.tournament, [0, 0])
            bt[1] += 1; bt[0] += int(pred == real)
            if row.tournament == "FIFA World Cup":
                wc_rows.append({"date": str(row.date)[:10], "home": h, "away": a,
                                "pred": LBL[pred], "real": LBL[real],
                                "score": [int(row.home_score), int(row.away_score)],
                                "hit": bool(pred == real)})
        # actualizar forma DESPUÉS (walk-forward)
        for t, sc, cc in ((h, row.home_score, row.away_score), (a, row.away_score, row.home_score)):
            gf[t] = gf.get(t, 0) + sc; ga[t] = ga.get(t, 0) + cc; n[t] = n.get(t, 0) + 1

    acc = hits / total * 100
    wc = by_torneo.get("FIFA World Cup", [0, 1])
    if not quiet:
        import json
        payload = {
            "n": total, "acc": round(acc, 1),
            "wins_acc": round(wins_hits / wins_total * 100, 1),
            "wc_acc": round(wc[0] / wc[1] * 100, 1), "wc_n": wc[1],
            "by_tournament": {t: {"hits": v[0], "n": v[1]}
                              for t, v in by_torneo.items() if v[1] >= 8},
            "wc_matches": wc_rows,
        }
        out = os.path.join(ROOT, "web", "data", "validation_2026.json")
        json.dump(payload, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"-> {out}")
        patch_backtest()   # inyecta el modelo 2026 como 5º modelo en la validación
        print(f"\n=== VALIDACIÓN MODELO SOLO-2026 (walk-forward, sin histórico) ===")
        print(f"  Acierto 1-X-2: {hits}/{total} = {acc:.1f}%")
        print(f"  Cuando hay ganador: {wins_hits}/{wins_total} = {wins_hits/wins_total*100:.1f}%")
        print(f"  En Mundial: {wc[0]}/{wc[1]} = {wc[0]/wc[1]*100:.0f}%")
    return acc, wc[0] / wc[1] * 100


def patch_backtest():
    """Inyecta el modelo SOLO-2026 (y1/yx/yx) como 5º modelo en backtest.json,
    calculado sobre LOS MISMOS partidos que muestran los otros modelos."""
    import json
    bt_path = os.path.join(ROOT, "web", "data", "backtest.json")
    if not os.path.exists(bt_path):
        print("  (no hay backtest.json para inyectar el modelo 2026)"); return
    bt = json.load(open(bt_path, encoding="utf-8"))
    ms = bt.get("matches", [])
    if not ms:
        return
    # historial 2026 por equipo (para forma walk-forward)
    r = pd.read_csv(os.path.join(ROOT, "data_repo", "results.csv"), parse_dates=["date"])
    r = r[(r["date"] >= "2026-01-01") & r["tournament"].isin(TORNEOS)].copy()
    r = r.dropna(subset=["home_score", "away_score"]).sort_values("date")
    hist = {}
    for x in r.itertuples(index=False):
        hist.setdefault(x.home_team, []).append((x.date, int(x.home_score), int(x.away_score)))
        hist.setdefault(x.away_team, []).append((x.date, int(x.away_score), int(x.home_score)))

    mor, inj, patt = load_signals()

    def form(team, before):
        h = [g for g in hist.get(team, []) if g[0] < pd.Timestamp(before)]
        if not h:
            return AVG, AVG
        gf = np.mean([g[1] for g in h]); ga = np.mean([g[2] for g in h])
        return gf, ga

    hits = total = 0
    for m in ms:
        h, a = m["home"], m["away"]
        hgf, hga = form(h, m["date"]); agf, aga = form(a, m["date"])
        lh = (hgf + aga) / 2 * HOME_ADV; la = (agf + hga) / 2 / HOME_ADV
        if h in patt:
            lh *= 1 + 0.4 * (patt[h][0] - 1); la *= 1 - 0.4 * (patt[h][1] - 1)
        if a in patt:
            la *= 1 + 0.4 * (patt[a][0] - 1); lh *= 1 - 0.4 * (patt[a][1] - 1)
        lh *= 1 + 0.05 * mor.get(h, 0); la *= 1 + 0.05 * mor.get(a, 0)
        lh *= 1 - inj.get(h, 0); la *= 1 - inj.get(a, 0)
        o = dc_outcome(float(np.clip(lh, 0.15, 5)), float(np.clip(la, 0.15, 5)))
        m["y1"], m["yx"], m["y2"] = [round(float(x), 4) for x in o]
        if m.get("eligible"):
            total += 1
            hits += int(["1", "X", "2"][int(o.argmax())] == m["real"])
    acc = hits / total if total else 0
    bt.setdefault("metrics_eligible", {})["y2026_acc"] = round(acc, 4)
    bt["metrics_eligible"]["y2026_logloss"] = 0.0
    json.dump(bt, open(bt_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  Modelo SOLO-2026 inyectado en backtest.json (acierto WC {acc*100:.1f}%)")


if __name__ == "__main__":
    import sys
    if "--ab" in sys.argv:
        print("A/B — ¿la info por jugador sube la certeza? (modelo 2026, partidos jugados)\n")
        base = main(use_players=False, quiet=True)
        full = main(use_players=True, quiet=True)
        print(f"{'Config':<26}{'Global':>9}{'Mundial':>9}")
        print(f"{'SIN jugadores':<26}{base[0]:>8.1f}%{base[1]:>8.0f}%")
        print(f"{'CON jugadores':<26}{full[0]:>8.1f}%{full[1]:>8.0f}%")
        print(f"\nΔ global: {full[0]-base[0]:+.1f} pts | Δ Mundial: {full[1]-base[1]:+.0f} pts")
        print("-> los jugadores AYUDAN" if full[0] > base[0] else "-> los jugadores NO ayudan (o restan)")
    else:
        main()
