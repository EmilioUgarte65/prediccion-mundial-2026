"""Descarga xG por partido de los Mundiales 2018 y 2022 desde StatsBomb Open Data.

Para cada partido baja sus eventos y suma el statsbomb_xg de los tiros por equipo.
Guarda data_user/sb_match_xg.csv con: season, date, home_team, away_team,
home_xg, away_xg, home_score, away_score (nombres normalizados a nuestro dataset).
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = os.path.dirname(os.path.dirname(__file__))
SB_DIR = os.path.join(ROOT, "sb_data")
OUT = os.path.join(ROOT, "data_user", "sb_match_xg.csv")

# StatsBomb -> nombres de nuestro dataset (martj42)
SB_ALIAS = {
    "Korea Republic": "South Korea", "IR Iran": "Iran", "China PR": "China PR",
    "Republic of Ireland": "Republic of Ireland", "United States": "United States",
}
SEASONS = {"2018": "3", "2022": "106"}


def norm(name: str) -> str:
    return SB_ALIAS.get(name, name)


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def match_xg(match_id: int):
    ev = fetch_json(f"{BASE}/events/{match_id}.json")
    xg = defaultdict(float)
    for e in ev:
        if e.get("type", {}).get("name") == "Shot":
            xg[e["team"]["name"]] += e.get("shot", {}).get("statsbomb_xg", 0.0)
    return xg


def main():
    rows = []
    for season, sid in SEASONS.items():
        matches = fetch_json(f"{BASE}/matches/43/{sid}.json")
        print(f"Mundial {season}: {len(matches)} partidos, bajando xG...")
        for i, m in enumerate(matches, 1):
            mid = m["match_id"]
            h = m["home_team"]["home_team_name"]
            a = m["away_team"]["away_team_name"]
            try:
                xg = match_xg(mid)
            except Exception as e:  # noqa: BLE001
                print(f"  fallo {mid}: {e}")
                continue
            rows.append({
                "season": season, "date": m["match_date"],
                "home_team": norm(h), "away_team": norm(a),
                "home_xg": round(xg.get(h, 0.0), 3), "away_xg": round(xg.get(a, 0.0), 3),
                "home_score": m["home_score"], "away_score": m["away_score"],
            })
            if i % 16 == 0:
                print(f"  {i}/{len(matches)}")

    import csv
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nOK -> {OUT}  ({len(rows)} partidos con xG)")


if __name__ == "__main__":
    main()
