"""#1 — XI CONFIRMADO en vivo (API-Football / RapidAPI).

Corre cada ~15 min: busca partidos del Mundial que empiezan en los próximos
~60 min y baja su alineación titular confirmada (startXI). Guarda
data_user/lineups_live.csv para que el motor recalcule justo antes del cierre.

Requiere en config/api_keys.json:  {"rapidapi": "TU_LLAVE"}
Liga API-Football del Mundial: id 1 (World Cup), temporada 2026.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(__file__))
KEYS = os.path.join(ROOT, "config", "api_keys.json")
OUT = os.path.join(ROOT, "data_user", "lineups_live.csv")
HOST = "api-football-v1.p.rapidapi.com"
LEAGUE_ID, SEASON = 1, 2026
WINDOW_MIN = 60  # baja XI de partidos que empiezan dentro de este margen


def _key():
    with open(KEYS, encoding="utf-8") as f:
        k = json.load(f).get("rapidapi")
    if not k:
        raise SystemExit("Falta 'rapidapi' en config/api_keys.json")
    return k


def _get(path, params):
    url = f"https://{HOST}/v3/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "x-rapidapi-key": _key(), "x-rapidapi-host": HOST})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["response"]


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fixtures = _get("fixtures", {"league": LEAGUE_ID, "season": SEASON, "date": today})
    now = datetime.now(timezone.utc)
    rows = []
    for fx in fixtures:
        ts = fx["fixture"]["timestamp"]
        mins_to = (datetime.fromtimestamp(ts, timezone.utc) - now).total_seconds() / 60
        if not (0 < mins_to <= WINDOW_MIN):
            continue
        fid = fx["fixture"]["id"]
        for side in _get("fixtures/lineups", {"fixture": fid}):
            team = side["team"]["name"]
            for p in side.get("startXI", []):
                pl = p["player"]
                rows.append({"fixture": fid, "team": team,
                             "player": pl["name"], "pos": pl.get("pos", ""),
                             "number": pl.get("number", "")})
    if rows:
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"OK -> {OUT} ({len(rows)} titulares de partidos inminentes)")
    else:
        print("Sin partidos en la ventana de 60 min (nada que actualizar).")


if __name__ == "__main__":
    main()
