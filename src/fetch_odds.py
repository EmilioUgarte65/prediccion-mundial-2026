"""Descarga cuotas del Mundial 2026 desde The Odds API y las guarda.

- h2h (1X2) por partido -> data_user/odds.csv (promedio de casas, des-vigorizado).
- Outright winner -> imprime prob. de campeón implícita del mercado para comparar.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
KEYS = json.load(open(os.path.join(ROOT, "config", "api_keys.json"), encoding="utf-8"))
KEY = KEYS["the_odds_api"]
ODDS_CSV = os.path.join(ROOT, "data_user", "odds.csv")
CHAMP_CSV = os.path.join(ROOT, "data_user", "champion_odds.csv")

# The Odds API -> nuestro dataset
ALIAS = {
    "USA": "United States", "Czechia": "Czech Republic",
    "Cote d'Ivoire": "Ivory Coast", "DR Congo": "DR Congo",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Korea Republic": "South Korea", "IR Iran": "Iran",
}


def norm(t):
    return ALIAS.get(t, t)


def get(url):
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.load(r)


def avg_h2h():
    url = (f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"
           f"?apiKey={KEY}&regions=eu&markets=h2h&oddsFormat=decimal")
    data = get(url)
    rows = []
    for m in data:
        h, a = m["home_team"], m["away_team"]
        acc = defaultdict(list)
        for bk in m["bookmakers"]:
            for mk in bk["markets"]:
                if mk["key"] != "h2h":
                    continue
                for o in mk["outcomes"]:
                    acc[o["name"]].append(o["price"])
        if not acc:
            continue
        def mean(name):
            v = acc.get(name, [])
            return sum(v) / len(v) if v else None
        oh, od, oa = mean(h), mean("Draw"), mean(a)
        if None in (oh, od, oa):
            continue
        rows.append({"date": m["commence_time"][:10],
                     "home_team": norm(h), "away_team": norm(a),
                     "odd_home": round(oh, 2), "odd_draw": round(od, 2),
                     "odd_away": round(oa, 2)})
    return rows


def devig(oh, od, oa):
    ph, pd, pa = 1 / oh, 1 / od, 1 / oa
    s = ph + pd + pa
    return ph / s, pd / s, pa / s


def fetch_champion():
    """Cuotas de campeón (outright) -> prob. implícita des-vig por equipo."""
    url = (f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup_winner/"
           f"odds/?apiKey={KEY}&regions=eu&markets=outrights&oddsFormat=decimal")
    try:
        data = get(url)
    except Exception as e:  # noqa: BLE001
        print("  ! champion odds:", e); return
    outs = data[0]["bookmakers"][0]["markets"][0]["outcomes"]
    tot = sum(1 / o["price"] for o in outs)
    rows = [{"team": norm(o["name"]), "market_champ": round(1 / o["price"] / tot, 4)}
            for o in outs]
    with open(CHAMP_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "market_champ"])
        w.writeheader(); w.writerows(rows)
    print(f"OK -> {CHAMP_CSV}  ({len(rows)} equipos)")


def main():
    fetch_champion()
    rows = avg_h2h()
    os.makedirs(os.path.dirname(ODDS_CSV), exist_ok=True)
    with open(ODDS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "home_team", "away_team",
                                          "odd_home", "odd_draw", "odd_away"])
        w.writeheader(); w.writerows(rows)
    print(f"OK -> {ODDS_CSV}  ({len(rows)} partidos con cuotas)\n")
    print("Probabilidades implícitas del mercado (des-vigorizadas):")
    for r in rows:
        ph, pd, pa = devig(r["odd_home"], r["odd_draw"], r["odd_away"])
        print(f"  {r['date']} {r['home_team']:>14} {ph*100:4.0f}% "
              f"X {pd*100:3.0f}% {pa*100:4.0f}% {r['away_team']:<14}")


if __name__ == "__main__":
    main()
