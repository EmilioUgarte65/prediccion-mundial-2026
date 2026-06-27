"""Descarga COMPLETA de StatsBomb (WC 2018/2022) en una sola pasada.

Por partido: xG, amarillas, rojas y faltas por equipo -> data_user/sb_match_stats.csv
Por tarjeta: minuto, equipo, jugador, tipo, y el resultado del partido
            -> data_user/sb_cards_detail.csv
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_MATCH = os.path.join(ROOT, "data_user", "sb_match_stats.csv")
OUT_CARDS = os.path.join(ROOT, "data_user", "sb_cards_detail.csv")
SEASONS = {"2018": "3", "2022": "106"}
SB_ALIAS = {"Korea Republic": "South Korea", "IR Iran": "Iran"}


def norm(t):
    return SB_ALIAS.get(t, t)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def card_of(e):
    for k in ("bad_behaviour", "foul_committed"):
        c = e.get(k, {}).get("card", {})
        if c:
            return c.get("name", "")
    return ""


def main():
    match_rows, card_rows = [], []
    for season, sid in SEASONS.items():
        matches = get(f"{BASE}/matches/43/{sid}.json")
        print(f"Mundial {season}: {len(matches)} partidos...")
        for i, m in enumerate(matches, 1):
            mid = m["match_id"]
            h = m["home_team"]["home_team_name"]; a = m["away_team"]["away_team_name"]
            hs, as_ = m["home_score"], m["away_score"]
            try:
                ev = get(f"{BASE}/events/{mid}.json")
            except Exception as e:  # noqa: BLE001
                print(f"  fallo {mid}: {e}"); continue
            xg = defaultdict(float); yel = defaultdict(int); red = defaultdict(int)
            foul = defaultdict(int)
            for e in ev:
                t = e.get("team", {}).get("name")
                if not t:
                    continue
                tn = e.get("type", {}).get("name")
                if tn == "Shot":
                    xg[t] += e.get("shot", {}).get("statsbomb_xg", 0.0)
                if tn == "Foul Committed":
                    foul[t] += 1
                cn = card_of(e)
                if cn:
                    is_red = cn in ("Red Card", "Second Yellow")
                    (red if is_red else yel)[t] += 1
                    card_rows.append({
                        "season": season, "date": m["match_date"],
                        "minute": e.get("minute", ""), "team": norm(t),
                        "player": e.get("player", {}).get("name", ""),
                        "type": "red" if is_red else "yellow",
                        "result": "H" if hs > as_ else ("A" if hs < as_ else "D"),
                        "is_home": int(t == h),
                    })
            match_rows.append({
                "season": season, "date": m["match_date"],
                "home_team": norm(h), "away_team": norm(a),
                "home_xg": round(xg.get(h, 0.0), 3), "away_xg": round(xg.get(a, 0.0), 3),
                "home_yellow": yel.get(h, 0), "away_yellow": yel.get(a, 0),
                "home_red": red.get(h, 0), "away_red": red.get(a, 0),
                "home_fouls": foul.get(h, 0), "away_fouls": foul.get(a, 0),
                "home_score": hs, "away_score": as_,
            })
            if i % 16 == 0:
                print(f"  {i}/{len(matches)}")

    for path, rows in ((OUT_MATCH, match_rows), (OUT_CARDS, card_rows)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"\nOK -> {OUT_MATCH} ({len(match_rows)} partidos)")
    print(f"OK -> {OUT_CARDS} ({len(card_rows)} tarjetas)")


if __name__ == "__main__":
    main()
