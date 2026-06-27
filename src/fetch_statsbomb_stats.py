"""Descarga xG y TARJETAS por partido de los Mundiales 2018/2022 (StatsBomb).

Por cada partido suma: xG (de los tiros) y tarjetas amarillas/rojas por equipo
(eventos 'Bad Behaviour' y 'Foul Committed' con tarjeta).
Guarda data_user/sb_match_stats.csv.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "sb_match_stats.csv")
SEASONS = {"2018": "3", "2022": "106"}
SB_ALIAS = {"Korea Republic": "South Korea", "IR Iran": "Iran"}


def norm(t):
    return SB_ALIAS.get(t, t)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def card_name(e):
    for k in ("bad_behaviour", "foul_committed"):
        c = e.get(k, {}).get("card", {})
        if c:
            return c.get("name", "")
    return ""


def match_stats(mid):
    ev = get(f"{BASE}/events/{mid}.json")
    xg = defaultdict(float); yel = defaultdict(int); red = defaultdict(int)
    for e in ev:
        t = e.get("team", {}).get("name")
        if not t:
            continue
        if e.get("type", {}).get("name") == "Shot":
            xg[t] += e.get("shot", {}).get("statsbomb_xg", 0.0)
        cn = card_name(e)
        if cn == "Yellow Card":
            yel[t] += 1
        elif cn in ("Red Card", "Second Yellow"):
            red[t] += 1
    return xg, yel, red


def main():
    rows = []
    for season, sid in SEASONS.items():
        matches = get(f"{BASE}/matches/43/{sid}.json")
        print(f"Mundial {season}: {len(matches)} partidos...")
        for i, m in enumerate(matches, 1):
            mid = m["match_id"]
            h = m["home_team"]["home_team_name"]; a = m["away_team"]["away_team_name"]
            try:
                xg, yel, red = match_stats(mid)
            except Exception as e:  # noqa: BLE001
                print(f"  fallo {mid}: {e}"); continue
            rows.append({
                "season": season, "date": m["match_date"],
                "home_team": norm(h), "away_team": norm(a),
                "home_xg": round(xg.get(h, 0.0), 3), "away_xg": round(xg.get(a, 0.0), 3),
                "home_yellow": yel.get(h, 0), "away_yellow": yel.get(a, 0),
                "home_red": red.get(h, 0), "away_red": red.get(a, 0),
                "home_score": m["home_score"], "away_score": m["away_score"],
            })
            if i % 16 == 0:
                print(f"  {i}/{len(matches)}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nOK -> {OUT}  ({len(rows)} partidos)")


if __name__ == "__main__":
    main()
