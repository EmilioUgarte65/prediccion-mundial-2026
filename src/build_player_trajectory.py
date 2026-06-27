"""Trayectoria por jugador convocado al Mundial 2026 (datos cacheados, sin API).

Cruza squads_2026.csv (convocados) con goalscorers.csv (historial de goles) y
guarda data_user/player_trajectory.csv con la trayectoria goleadora de cada
jugador: goles de carrera, por ventana reciente, en este Mundial, años activos.

Nota honesta: goalscorers solo registra GOLES (no apariciones), así que la
trayectoria es goleadora; porteros/defensas sin goles quedan con 0.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict

import pandas as pd

from data_prep import load_goalscorers

ROOT = os.path.dirname(os.path.dirname(__file__))
SQUADS = os.path.join(ROOT, "data_user", "squads_2026.csv")
OUT = os.path.join(ROOT, "data_user", "player_trajectory.csv")
PERF = os.path.join(ROOT, "web", "data", "player_performance.json")
TODAY = pd.Timestamp("2026-06-26")


def _age(dob):
    try:
        d = pd.Timestamp(dob)
        return int((TODAY - d).days // 365.25)
    except Exception:  # noqa: BLE001
        return None


def _fatigue(age, years):
    """Indicador de desgaste: edad + rendimiento reciente vs pico goleador."""
    if age is None or age < 33 or not years:
        return "baja"
    per_year = Counter(years)
    peak = max(per_year.values())
    recent = sum(1 for y in years if y >= 2024) / 2.5   # goles/año recientes
    ratio = recent / max(peak, 1)
    if ratio < 0.4:
        return "alta"
    if ratio < 0.75:
        return "media"
    return "baja"


def main():
    g = load_goalscorers()
    g = g[g["own_goal"] != True]  # noqa: E712
    by_player = defaultdict(list)        # nombre -> [(year, is_pen, is_wc)]
    for r in g.itertuples(index=False):
        by_player[r.scorer].append((r.date.year, r.penalty is True,
                                    r.date >= __import__("pandas").Timestamp("2026-06-01")))

    rows = []
    with open(SQUADS, encoding="utf-8") as f:
        squad = list(csv.DictReader(f))
    for p in squad:
        name = p["player"]
        gl = by_player.get(name, [])
        years = [y for y, _, _ in gl]
        age = _age(p.get("dob", ""))
        rows.append({
            "team": p["team"], "player": name, "position": p["position"],
            "age": age if age is not None else "",
            "career_goals": len(gl),
            "goals_2024_26": sum(1 for y in years if y >= 2024),
            "goals_wc2026": sum(1 for _, _, wc in gl if wc),
            "pen_goals": sum(1 for _, pen, _ in gl if pen),
            "first_year": min(years) if years else "",
            "last_year": max(years) if years else "",
            "fatigue": _fatigue(age, years),
        })
    rows.sort(key=lambda r: r["career_goals"], reverse=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    scored = sum(1 for r in rows if r["career_goals"] > 0)
    print(f"OK -> {OUT}  ({len(rows)} convocados, {scored} con goles)")

    # Veteranos (33+) con goles -> JSON para la web (rendimiento/fatiga)
    vets = [r for r in rows if isinstance(r["age"], int) and r["age"] >= 33
            and r["career_goals"] >= 8]
    vets.sort(key=lambda r: r["career_goals"], reverse=True)
    perf = [{"player": r["player"], "team": r["team"], "age": r["age"],
             "career_goals": r["career_goals"], "goals_2024_26": r["goals_2024_26"],
             "fatigue": r["fatigue"]} for r in vets[:18]]
    os.makedirs(os.path.dirname(PERF), exist_ok=True)
    with open(PERF, "w", encoding="utf-8") as f:
        json.dump({"updated": str(TODAY.date()), "veterans": perf}, f,
                  ensure_ascii=False, indent=2)
    print(f"OK -> {PERF}  ({len(perf)} veteranos)")
    for r in vets[:6]:
        print(f"  {r['player']:<20} ({r['age']}) goles24-26={r['goals_2024_26']} "
              f"desgaste={r['fatigue']}")


if __name__ == "__main__":
    main()
