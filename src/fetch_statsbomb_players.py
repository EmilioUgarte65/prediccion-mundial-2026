"""Stats POR JUGADOR de los Mundiales 2018/2022 (StatsBomb) -> pedigrí mundialista.

Para cada jugador suma, sobre ambos Mundiales: xG, goles, tiros y asistencias.
Se cruzará con los convocados 2026 (muchos veteranos repiten).
Guarda data_user/sb_players_hist.csv.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "sb_players_hist.csv")
SEASONS = {"2018": "3", "2022": "106"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    xg = defaultdict(float); goals = defaultdict(int)
    shots = defaultdict(int); assists = defaultdict(int)
    team_of = {}
    for season, sid in SEASONS.items():
        matches = get(f"{BASE}/matches/43/{sid}.json")
        print(f"Mundial {season}: {len(matches)} partidos...")
        for i, m in enumerate(matches, 1):
            try:
                ev = get(f"{BASE}/events/{m['match_id']}.json")
            except Exception as e:  # noqa: BLE001
                print(f"  fallo {m['match_id']}: {e}"); continue
            for e in ev:
                p = e.get("player", {}).get("name")
                if not p:
                    continue
                team_of[p] = e.get("team", {}).get("name", team_of.get(p, ""))
                tn = e.get("type", {}).get("name")
                if tn == "Shot":
                    sh = e.get("shot", {})
                    xg[p] += sh.get("statsbomb_xg", 0.0); shots[p] += 1
                    if sh.get("outcome", {}).get("name") == "Goal":
                        goals[p] += 1
                elif tn == "Pass" and e.get("pass", {}).get("goal_assist"):
                    assists[p] += 1
            if i % 16 == 0:
                print(f"  {i}/{len(matches)}")
    players = sorted(xg.keys() | goals.keys() | assists.keys())
    rows = [{"player": p, "team_2018_22": team_of.get(p, ""),
             "wc_xg": round(xg.get(p, 0.0), 2), "wc_goals": goals.get(p, 0),
             "wc_shots": shots.get(p, 0), "wc_assists": assists.get(p, 0)}
            for p in players]
    rows.sort(key=lambda r: r["wc_xg"], reverse=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nOK -> {OUT}  ({len(rows)} jugadores con datos StatsBomb 2018/22)")


if __name__ == "__main__":
    main()
