"""#2 — Valor de mercado por selección (API local de Transfermarkt).

Requiere el contenedor levantado (docker/transfermarkt-compose.yml) en :8011.
Flujo: busca cada selección -> obtiene su squad -> suma el valor de mercado.
Guarda data_user/market_values.csv (team, squad_value_eur, top_player, top_value).

El valor de mercado es señal fuerte de calidad de plantel (forward 2026).
"""
from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "market_values.csv")
BASE = "http://localhost:8011"


def _get(path):
    url = BASE + path
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def _parse_eur(v):
    """'€80.00m' / '€900k' -> float en euros."""
    if not v:
        return 0.0
    s = str(v).replace("€", "").strip().lower()
    mult = 1.0
    if s.endswith("m"):
        mult, s = 1e6, s[:-1]
    elif s.endswith("k"):
        mult, s = 1e3, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def squad_value(team_name):
    """Busca la selección y suma el valor de su plantel actual."""
    res = _get("/competitions/search/" + urllib.parse.quote(team_name))
    # transfermarkt-api: usar /clubs/search para selecciones nacionales
    clubs = _get("/clubs/search/" + urllib.parse.quote(team_name)).get("results", [])
    if not clubs:
        return None
    cid = clubs[0]["id"]
    players = _get(f"/clubs/{cid}/players").get("players", [])
    total = 0.0; top = ("", 0.0)
    for p in players:
        v = _parse_eur(p.get("marketValue"))
        total += v
        if v > top[1]:
            top = (p.get("name", ""), v)
    return {"team": team_name, "squad_value_eur": int(total),
            "top_player": top[0], "top_value": int(top[1])}


def main():
    # selecciones del Mundial (de squads_2026)
    sq = os.path.join(ROOT, "data_user", "squads_2026.csv")
    teams = sorted({r["team"] for r in csv.DictReader(open(sq, encoding="utf-8"))})
    rows = []
    for t in teams:
        try:
            r = squad_value(t)
            if r:
                rows.append(r); print(f"  {t}: €{r['squad_value_eur']/1e6:.0f}M")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {t}: {e}")
    if rows:
        with open(OUT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nOK -> {OUT} ({len(rows)} selecciones)")


if __name__ == "__main__":
    main()
