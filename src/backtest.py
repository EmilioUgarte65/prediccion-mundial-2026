"""Validación walk-forward: predecir partidos YA jugados con info previa.

Para cada Mundial (2018, 2022, 2026) entrena el modelo SOLO con datos anteriores
al torneo (sin fuga) y predice sus partidos, comparando vs la realidad.
Compara 3 enfoques: estadístico (Dixon-Coles), predictivo (XGBoost) y ensemble.

Se evalúa desde el 2º partido de cada selección en ese torneo.
Guarda web/data/backtest.json (Mundial 2026) para la web.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy.stats import poisson

from data_prep import load_results
from ratings import compute_elo, GoalsModel
from model import FeatureBuilder, WCModel, FEATURES
from statmodel import StatModel
from elomodel import EloModel

OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "web", "data", "backtest.json")
LABELS = {0: "1", 1: "X", 2: "2"}

MIN_YEAR = 1970  # validar Mundiales desde este año (entrenamiento progresivo)


def detect_editions(results, min_year=MIN_YEAR):
    """Detecta automáticamente cada edición del Mundial y su rango de fechas."""
    wc = results[results["tournament"] == "FIFA World Cup"].copy()
    wc["year"] = wc["date"].dt.year
    eds = []
    for y, g in wc.groupby("year"):
        if int(y) >= min_year:
            eds.append((str(int(y)), str(g["date"].min().date()),
                        str(g["date"].max().date())))
    return eds


def most_likely_score(lh, la, maxg=8):
    grid = np.outer(poisson.pmf(np.arange(maxg + 1), lh),
                    poisson.pmf(np.arange(maxg + 1), la))
    i, j = np.unravel_index(grid.argmax(), grid.shape)
    return int(i), int(j)


def backtest_one(results, elo, start, end):
    cutoff = pd.Timestamp(start)
    pre = results[results["date"] < cutoff].copy()
    gm = GoalsModel().fit(pre)
    fb = FeatureBuilder(gm)
    feats = fb.build_training(results)
    feats["date"] = results["date"].to_numpy()

    pre_mask = results["date"].to_numpy() < np.datetime64(cutoff)
    model = WCModel().train(feats[pre_mask].reset_index(drop=True))

    stat = StatModel(gm)
    samp = feats[pre_mask].tail(4000)
    stat.fit_rho(samp["lam_h"].to_numpy(), samp["lam_a"].to_numpy(),
                 samp["label"].to_numpy().astype(int))

    # modelo Elo (con curva de empate) ajustado con datos previos
    pre_res = results[pre_mask]
    lab_pre = np.where(pre_res["home_score"] > pre_res["away_score"], 0,
                       np.where(pre_res["home_score"] < pre_res["away_score"], 2, 1))
    elom = EloModel().fit(pre_res["home_elo"].to_numpy(), pre_res["away_elo"].to_numpy(),
                          pre_res["neutral"].to_numpy(), lab_pre)

    wc_idx = results.index[(results["tournament"] == "FIFA World Cup")
                           & (results["date"] >= cutoff)
                           & (results["date"] <= pd.Timestamp(end))].tolist()
    played = {}
    rows = []
    for idx in wc_idx:
        r = results.loc[idx]
        h, a = r["home_team"], r["away_team"]
        nh, na = played.get(h, 0), played.get(a, 0)
        feat_row = feats.loc[idx, FEATURES].to_dict()
        px = model.predict_outcome(feat_row)
        lh, la = model.predict_lambdas(feat_row)
        sp = stat.outcome_from_lambdas(feats.loc[idx, "lam_h"], feats.loc[idx, "lam_a"])
        ep = elom.outcome_probs(r["home_elo"], r["away_elo"], bool(r["neutral"]))
        ens = (px + sp + ep) / 3.0
        pscore = most_likely_score(lh, la)
        real = 0 if r["home_score"] > r["away_score"] else (
               2 if r["home_score"] < r["away_score"] else 1)
        rows.append({
            "date": str(r["date"].date()), "home": h, "away": a,
            "p1": round(float(px[0]), 4), "px": round(float(px[1]), 4), "p2": round(float(px[2]), 4),
            "s1": round(float(sp[0]), 4), "sx": round(float(sp[1]), 4), "s2": round(float(sp[2]), 4),
            "el1": round(float(ep[0]), 4), "elx": round(float(ep[1]), 4), "el2": round(float(ep[2]), 4),
            "e1": round(float(ens[0]), 4), "ex": round(float(ens[1]), 4), "e2": round(float(ens[2]), 4),
            "pred": LABELS[int(px.argmax())], "pred_score": list(pscore),
            "real_score": [int(r["home_score"]), int(r["away_score"])], "real": LABELS[real],
            "hit": bool(int(px.argmax()) == real),
            "exact": bool(pscore == (int(r["home_score"]), int(r["away_score"]))),
            "eligible": bool(nh >= 1 and na >= 1),
            "elo_home": round(float(r["home_elo"]), 0), "elo_away": round(float(r["away_elo"]), 0),
        })
        played[h] = nh + 1; played[a] = na + 1
    return rows, model.metrics


def _scores(P, y):
    pred = P.argmax(1)
    acc = float((pred == y).mean())
    ll = float(-np.mean(np.log(np.clip(P[np.arange(len(y)), y], 1e-15, 1))))
    oh = np.zeros_like(P); oh[np.arange(len(y)), y] = 1
    br = float(np.mean(np.sum((P - oh) ** 2, axis=1)))
    return round(acc, 4), round(ll, 4), round(br, 4)


def metrics_for(rows):
    if not rows:
        return {}
    y = np.array([{"1": 0, "X": 1, "2": 2}[r["real"]] for r in rows])
    Px = np.array([[r["p1"], r["px"], r["p2"]] for r in rows])
    Ps = np.array([[r["s1"], r["sx"], r["s2"]] for r in rows])
    Pel = np.array([[r["el1"], r["elx"], r["el2"]] for r in rows])
    Pe = np.array([[r["e1"], r["ex"], r["e2"]] for r in rows])
    elo_fav = np.array([0 if r["elo_home"] >= r["elo_away"] else 2 for r in rows])
    pred_sc = np.array([r["pred_score"] for r in rows])
    real_sc = np.array([r["real_score"] for r in rows])
    out = {"n": len(rows),
           "baseline_elo_acc": round(float((elo_fav == y).mean()), 4),
           "goals_mae": round(float(np.mean(np.abs(pred_sc - real_sc))), 4),
           "exact_score": round(float(np.mean([r["exact"] for r in rows])), 4)}
    for name, P in (("stat", Ps), ("xgb", Px), ("elo", Pel), ("ens", Pe)):
        acc, ll, br = _scores(P, y)
        out[f"{name}_acc"] = acc; out[f"{name}_logloss"] = ll; out[f"{name}_brier"] = br
    return out


def show(tag, m):
    if not m:
        print(f"\n[{tag}] sin partidos."); return
    print(f"\n=== Mundial {tag}  ({m['n']} partidos, desde 2º de c/selección) ===")
    print(f"  {'Modelo':<13}{'Acierto':>9}{'LogLoss':>10}{'Brier':>9}")
    for name, lab in (("stat", "Estadístico"), ("xgb", "XGBoost"), ("ens", "Ensemble")):
        print(f"  {lab:<13}{m[name+'_acc']*100:>8.1f}%{m[name+'_logloss']:>10.3f}{m[name+'_brier']:>9.3f}")
    print(f"  {'Baseline Elo':<13}{m['baseline_elo_acc']*100:>8.1f}%   |  exacto {m['exact_score']*100:.1f}%  MAE {m['goals_mae']}")


def _PY(rows):
    """Devuelve (Pelo, Pstat, Pxgb, y) como arrays."""
    y = np.array([{"1": 0, "X": 1, "2": 2}[r["real"]] for r in rows])
    Pel = np.array([[r["el1"], r["elx"], r["el2"]] for r in rows])
    Ps = np.array([[r["s1"], r["sx"], r["s2"]] for r in rows])
    Px = np.array([[r["p1"], r["px"], r["p2"]] for r in rows])
    return Pel, Ps, Px, y


def _acc_ll(P, y):
    acc = float((P.argmax(1) == y).mean())
    ll = float(-np.mean(np.log(np.clip(P[np.arange(len(y)), y], 1e-15, 1))))
    return acc, ll


def tune_ensemble(pooled):
    """Tunea pesos (elo,stat,xgb) en Mundiales 1998-2014 y mide en 2018-2026."""
    dev = [r for r in pooled if int(r["edition"]) <= 2014]
    test = [r for r in pooled if int(r["edition"]) >= 2018]
    if not dev or not test:
        return
    Pel_d, Ps_d, Px_d, y_d = _PY(dev)
    Pel_t, Ps_t, Px_t, y_t = _PY(test)

    best = None
    for we in np.arange(0, 1.01, 0.1):
        for ws in np.arange(0, 1.01 - we, 0.1):
            wx = 1 - we - ws
            if wx < -1e-9:
                continue
            P = we * Pel_d + ws * Ps_d + wx * Px_d
            _, ll = _acc_ll(P, y_d)          # optimizar log-loss en dev
            if best is None or ll < best[0]:
                best = (ll, we, ws, wx)
    _, we, ws, wx = best

    print("\n" + "=" * 64)
    print("EXPERIMENTO ENSEMBLE — tuneado en 1998-2014, medido en 2018-2026")
    print(f"  Pesos óptimos (dev): Elo={we:.1f}  Estadístico={ws:.1f}  XGBoost={wx:.1f}")
    print(f"\n  {'Modelo':<22}{'Acierto TEST':>13}{'LogLoss':>10}")
    for name, P in (("Elo", Pel_t), ("Estadístico", Ps_t), ("XGBoost", Px_t),
                    ("Ensemble (1/3 c/u)", (Pel_t + Ps_t + Px_t) / 3),
                    ("Ensemble TUNEADO", we * Pel_t + ws * Ps_t + wx * Px_t)):
        acc, ll = _acc_ll(P, y_t)
        print(f"  {name:<22}{acc*100:>12.1f}%{ll:>10.3f}")
    return we, ws, wx


def export_predictions(pooled, we, ws, wx):
    """Guarda todas las predicciones (modelo final) de todos los Mundiales."""
    out = os.path.join(ROOT_DATA, "wc_backtest_all.csv")
    lab = {0: "1", 1: "X", 2: "2"}
    per_wc = {}
    rows = []
    for r in pooled:
        P = [we * r["el1"] + ws * r["s1"] + wx * r["p1"],
             we * r["elx"] + ws * r["sx"] + wx * r["px"],
             we * r["el2"] + ws * r["s2"] + wx * r["p2"]]
        k = max(range(3), key=lambda i: P[i])
        pred = lab[k]
        hit = pred == r["real"]
        ed = r["edition"]
        per_wc.setdefault(ed, [0, 0])
        per_wc[ed][0] += int(hit); per_wc[ed][1] += 1
        rows.append({"mundial": ed, "fecha": r["date"], "local": r["home"],
                     "visitante": r["away"], "pred": pred,
                     "prob": round(P[k], 3), "real": r["real"],
                     "marcador": f"{r['real_score'][0]}-{r['real_score'][1]}",
                     "acierto": int(hit)})
    import csv
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nMODELO FINAL (ensemble Elo {we:.1f}/Stat {ws:.1f}/XGB {wx:.1f}) "
          f"— acierto por Mundial:")
    for ed in sorted(per_wc):
        h, n = per_wc[ed]
        print(f"  {ed}: {h}/{n} = {h/n*100:.1f}%")
    th = sum(v[0] for v in per_wc.values()); tn = sum(v[1] for v in per_wc.values())
    print(f"  GLOBAL: {th}/{tn} = {th/tn*100:.1f}%")
    print(f"  -> {out}")


ROOT_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_user")

CHAMPIONS = {  # campeones reales (para medir si atinamos al ganador del Mundial)
    "1970": "Brazil", "1974": "West Germany", "1978": "Argentina",
    "1982": "Italy", "1986": "Argentina", "1990": "West Germany",
    "1994": "Brazil", "1998": "France", "2002": "Brazil", "2006": "Italy",
    "2010": "Spain", "2014": "Germany", "2018": "France", "2022": "Argentina",
}


def _norm(s):
    return str(s).lower().replace("west ", "").strip()


def draw_threshold_experiment(pooled, we, ws, wx):
    """¿Predecir empate cuando P(X) es alta sube el acierto global histórico?"""
    P = np.array([[we * r["el1"] + ws * r["s1"] + wx * r["p1"],
                   we * r["elx"] + ws * r["sx"] + wx * r["px"],
                   we * r["el2"] + ws * r["s2"] + wx * r["p2"]] for r in pooled])
    P = P / P.sum(1, keepdims=True)
    y = np.array([{"1": 0, "X": 1, "2": 2}[r["real"]] for r in pooled])
    base = (P.argmax(1) == y).mean()
    print("\n" + "=" * 64)
    print(f"EXPERIMENTO EMPATES — {len(y)} partidos (todos los Mundiales)")
    print(f"  Base (argmax, nunca predice empate): {base*100:.2f}%  "
          f"(empates reales: {(y==1).mean()*100:.0f}%)")
    best = (base, None)
    for tau in np.arange(0.26, 0.40, 0.01):
        pred = np.where(P[:, 1] >= tau, 1, np.where(P[:, 0] >= P[:, 2], 0, 2))
        acc = (pred == y).mean()
        if acc > best[0] + 1e-9:
            best = (acc, float(tau))
        print(f"    umbral {tau:.2f}: {acc*100:.2f}%  "
              f"(predice {(pred==1).sum()} empates, acierta {int(((pred==1)&(y==1)).sum())})")
    if best[1]:
        print(f"  >> MEJOR umbral {best[1]:.2f}: {best[0]*100:.2f}% "
              f"(+{(best[0]-base)*100:.2f} pts vs base)")
    else:
        print("  >> Ningún umbral supera al base: predecir empates NO ayuda en el histórico.")
    return best


def champion_experiment(results, editions):
    """¿El favorito pre-torneo (mayor Elo) coincide con el campeón real?"""
    print("\n" + "=" * 64)
    print("EXPERIMENTO CAMPEÓN — favorito pre-torneo (Elo) vs campeón real")
    hits = tot = 0
    for tag, start, end in editions:
        if tag not in CHAMPIONS:
            continue
        pre = results[results["date"] < start]
        elo = {}
        for r in pre.itertuples(index=False):
            elo[r.home_team] = r.home_elo
            elo[r.away_team] = r.away_elo
        ed = results[(results["tournament"] == "FIFA World Cup")
                     & (results["date"] >= start) & (results["date"] <= end)]
        part = set(ed["home_team"]) | set(ed["away_team"])
        cand = sorted(((t, elo.get(t, 1500)) for t in part),
                      key=lambda x: x[1], reverse=True)
        fav = cand[0][0]
        champ = CHAMPIONS[tag]
        ok = _norm(fav) == _norm(champ)
        hits += ok; tot += 1
        top3 = ", ".join(f"{t}" for t, _ in cand[:3])
        print(f"  {tag}: favorito {fav:<14} campeón {champ:<14} {'✓' if ok else '✗'}"
              f"   (top3 Elo: {top3})")
    print(f"\n  Favorito pre-torneo = campeón: {hits}/{tot} = {hits/tot*100:.0f}%")
    print("  (Acertar al campeón es durísimo: el favorito gana ~1 de cada 3-4 Mundiales)")


def main():
    print("Cargando datos y Elo walk-forward...")
    results = load_results()
    results, elo = compute_elo(results)
    editions = detect_editions(results)
    print(f"Mundiales a validar: {[e[0] for e in editions]}")

    all_metrics = {}
    pooled = []          # todos los partidos elegibles de todos los Mundiales
    rows_2026 = None
    train_2026 = {}
    for tag, start, end in editions:
        print(f"\nEntrenando y validando Mundial {tag} (corte {start})...")
        rows, train_m = backtest_one(results, elo, start, end)
        elig = [r for r in rows if r["eligible"]]
        for r in elig:
            r["edition"] = tag
        m = metrics_for(elig)
        all_metrics[tag] = m
        pooled.extend(elig)
        show(tag, m)
        if tag == "2026":
            rows_2026, train_2026 = rows, train_m

    # ---- EXPERIMENTO: tunear pesos del ensemble en dev, medir en test ----
    weights = tune_ensemble(pooled) or (0.7, 0.0, 0.3)
    we, ws, wx = weights

    # ---- exportar TODAS las predicciones (modelo final = ensemble tuneado) ----
    export_predictions(pooled, we, ws, wx)

    # ---- EXPERIMENTOS pedidos: empates en histórico + acierto de campeón ----
    draw_threshold_experiment(pooled, we, ws, wx)
    champion_experiment(results, editions)

    # ---- métricas GLOBALES agrupando todos los Mundiales ----
    glob = metrics_for(pooled)
    print("\n" + "=" * 64)
    print(f"GLOBAL — TODOS LOS MUNDIALES {editions[0][0]}-{editions[-1][0]} "
          f"({glob['n']} partidos)")
    print(f"  Estadístico {glob['stat_acc']*100:.1f}%  |  "
          f"XGBoost {glob['xgb_acc']*100:.1f}%  |  "
          f"Ensemble {glob['ens_acc']*100:.1f}%  |  "
          f"Baseline Elo {glob['baseline_elo_acc']*100:.1f}%")
    print(f"  LogLoss(xgb) {glob['xgb_logloss']:.3f} · Brier {glob['xgb_brier']:.3f} "
          f"· marcador exacto {glob['exact_score']*100:.1f}%")
    print("\nAcierto por Mundial (ensemble / xgb / stat):")
    for tag in all_metrics:
        m = all_metrics[tag]
        if m:
            print(f"  {tag}: {m['ens_acc']*100:5.1f}% / {m['xgb_acc']*100:5.1f}% / "
                  f"{m['stat_acc']*100:5.1f}%   (baseline {m['baseline_elo_acc']*100:.1f}%)")

    if rows_2026 is not None:
        payload = {
            "meta": {"description": "Backtest walk-forward en todos los Mundiales",
                     "train_metrics": train_2026,
                     "global": glob,
                     "tournaments": all_metrics},
            "metrics_eligible": all_metrics.get("2026", glob),
            "matches": rows_2026,
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nOK -> {OUT_PATH}")


if __name__ == "__main__":
    main()
