"""Descarga los planteles (convocatorias) del Mundial 2026 desde Football-Data.org.

Guarda data_user/squads_2026.csv: team, player, position, dob, nationality.
Es la lista de CADA jugador seleccionado (48 equipos x ~26).
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
KEYS = json.load(open(os.path.join(ROOT, "config", "api_keys.json"), encoding="utf-8"))
TOKEN = KEYS["football_data_org"]
OUT = os.path.join(ROOT, "data_user", "squads_2026.csv")


def get(url):
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    data = get("https://api.football-data.org/v4/competitions/WC/teams?season=2026")
    rows = []
    for t in data["teams"]:
        for p in t.get("squad", []):
            rows.append({
                "team": t["name"], "player": p.get("name", ""),
                "position": p.get("position", ""), "dob": p.get("dateOfBirth", ""),
                "nationality": p.get("nationality", ""),
            })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "player", "position", "dob", "nationality"])
        w.writeheader(); w.writerows(rows)
    teams = len({r["team"] for r in rows})
    print(f"OK -> {OUT}  ({len(rows)} jugadores, {teams} equipos)")


if __name__ == "__main__":
    main()
