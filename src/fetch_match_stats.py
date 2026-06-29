"""Automatización: extrae TODO de cada partido del Mundial 2026 vía la API JSON
de ESPN (sin histórico). Para cada partido jugado guarda:

  data_user/match_team_stats_2026.csv  -> stats por equipo (posesión, remates, ...)
  data_user/player_match_stats_2026.csv-> stats por jugador por partido
  data_user/lineups_2026.csv           -> alineación + formación + titular/suplente
  data_user/events_2026.csv            -> cronología (goles, tarjetas, cambios)

Fuente: ESPN (site.api.espn.com), liga fifa.world. Gratis y automatizable.
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(ROOT, "data_user")
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
START = date(2026, 6, 11)        # inicio del Mundial
END = date(2026, 6, 28)          # hoy (se amplía solo al correr más adelante)

CANON = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Czechia": "Czech Republic",
    "Korea Republic": "South Korea", "Congo DR": "DR Congo",
    "Cape Verde Islands": "Cape Verde", "Türkiye": "Turkey", "IR Iran": "Iran",
}


def canon(n):
    return CANON.get((n or "").strip(), (n or "").strip())


def get(url):
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return None


def game_ids():
    """Recorre las fechas y junta los gameId de partidos FINALIZADOS."""
    ids = []
    d = START
    while d <= END:
        sb = get(f"{BASE}/scoreboard?dates={d.strftime('%Y%m%d')}")
        for e in (sb or {}).get("events", []):
            st = e.get("status", {}).get("type", {}).get("state")
            if st == "post":  # finalizado
                ids.append(e["id"])
        d += timedelta(days=1)
    return ids


def main():
    ids = game_ids()
    print(f"Partidos finalizados encontrados: {len(ids)}")
    team_rows, player_rows, lineup_rows, event_rows = [], [], [], []

    for gid in ids:
        d = get(f"{BASE}/summary?event={gid}")
        if not d:
            continue
        dt = d.get("header", {}).get("competitions", [{}])[0].get("date", "")[:10]
        bs = d.get("boxscore", {})
        teams = bs.get("teams", [])
        names = {}
        for t in teams:
            tn = canon(t.get("team", {}).get("displayName"))
            names[t.get("team", {}).get("id")] = tn
            row = {"gameId": gid, "date": dt, "team": tn}
            for s in t.get("statistics", []):
                row[s.get("name")] = s.get("displayValue")
            team_rows.append(row)
        # alineaciones + stats por jugador
        for r in d.get("rosters", []):
            tn = canon(r.get("team", {}).get("displayName"))
            formation = r.get("formation", "")
            for p in r.get("roster", []):
                ath = p.get("athlete", {})
                base = {"gameId": gid, "date": dt, "team": tn,
                        "player": ath.get("displayName", ""),
                        "pos": (p.get("position") or {}).get("abbreviation", ""),
                        "starter": bool(p.get("starter")),
                        "formation": formation}
                lineup_rows.append(dict(base))
                prow = dict(base)
                for s in p.get("stats", []):
                    prow[s.get("name")] = s.get("value")
                player_rows.append(prow)
        # cronología
        for ev in d.get("keyEvents", []):
            t = ev.get("team", {}) or {}
            ath = (ev.get("participants") or [{}])[0].get("athlete", {}) if ev.get("participants") else {}
            event_rows.append({
                "gameId": gid, "minute": (ev.get("clock") or {}).get("displayValue", ""),
                "type": (ev.get("type") or {}).get("text", ""),
                "team": canon(t.get("displayName")),
                "player": ath.get("displayName", ""),
                "text": ev.get("text", "")})
        time.sleep(0.4)

    def save(name, rows):
        if not rows:
            print(f"  (sin filas para {name})"); return
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        path = os.path.join(DATA, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
        print(f"  OK -> {name} ({len(rows)} filas)")

    save("match_team_stats_2026.csv", team_rows)
    save("player_match_stats_2026.csv", player_rows)
    save("lineups_2026.csv", lineup_rows)
    save("events_2026.csv", event_rows)
    print("Listo: datos 2026 (equipo, jugador, alineación, cronología) extraídos de ESPN.")


if __name__ == "__main__":
    main()
