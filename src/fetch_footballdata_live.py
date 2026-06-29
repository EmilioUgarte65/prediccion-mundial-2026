"""Datos REALES del Mundial 2026 desde football-data.org (infrautilizada).

Baja: goleadores reales, árbitros por partido y resultados.
Guarda data_user/scorers_real_2026.csv y data_user/referees_real_2026.csv.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
KEY = json.load(open(os.path.join(ROOT, "config", "api_keys.json"),
                    encoding="utf-8"))["football_data_org"]


def get(path):
    req = urllib.request.Request("https://api.football-data.org/v4/" + path,
                                 headers={"X-Auth-Token": KEY})
    return json.load(urllib.request.urlopen(req, timeout=30))


# nombres football-data -> canónicos del motor (un solo lugar de verdad)
FDCANON = {
    "Congo DR": "DR Congo", "Cape Verde Islands": "Cape Verde",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Türkiye": "Turkey",
    "Czechia": "Czech Republic", "Korea Republic": "South Korea", "IR Iran": "Iran",
}


def cz(n):
    return FDCANON.get(n, n)


def main():
    # Goleadores reales (equipo canónico desde el origen)
    sc = get("competitions/WC/scorers?limit=30")["scorers"]
    srows = [{"player": s["player"]["name"], "team": cz(s["team"]["name"]),
              "goals": s.get("goals") or 0, "assists": s.get("assists") or 0,
              "penalties": s.get("penalties") or 0} for s in sc]
    p = os.path.join(ROOT, "data_user", "scorers_real_2026.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(srows[0].keys()))
        w.writeheader(); w.writerows(srows)
    print(f"OK -> {p} ({len(srows)} goleadores reales)")

    # Árbitros por partido jugado
    ms = get("competitions/WC/matches")["matches"]
    rrows = []
    for m in ms:
        if m["status"] != "FINISHED":
            continue
        refs = m.get("referees", [])
        main_ref = refs[0]["name"] if refs else ""
        rrows.append({"home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                      "stage": m.get("stage", ""), "group": m.get("group") or "",
                      "referee": main_ref,
                      "ref_country": refs[0].get("nationality", "") if refs else ""})
    p2 = os.path.join(ROOT, "data_user", "referees_real_2026.csv")
    with open(p2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rrows[0].keys()))
        w.writeheader(); w.writerows(rrows)
    nref = sum(1 for r in rrows if r["referee"])
    print(f"OK -> {p2} ({len(rrows)} partidos, {nref} con árbitro)")

    # JSON para la web (goleadores + árbitros más frecuentes)
    from collections import Counter
    top = [{"player": s["player"]["name"], "team": s["team"]["name"],
            "goals": s.get("goals") or 0, "assists": s.get("assists") or 0}
           for s in sc[:12]]
    rc = Counter(r["referee"] for r in rrows if r["referee"])
    busy = [{"referee": k, "matches": v} for k, v in rc.most_common(6)]
    webp = os.path.join(ROOT, "web", "data", "real_2026.json")
    with open(webp, "w", encoding="utf-8") as f:
        json.dump({"scorers": top, "referees": busy, "n_ref_matches": nref},
                  f, ensure_ascii=False, indent=2)
    print(f"OK -> {webp}")

    # Cruces REALES de eliminatorias (para corregir la siembra del bracket)
    ko = [m for m in ms if m["stage"] in ("LAST_32", "LAST_16", "QUARTER_FINALS",
                                          "SEMI_FINALS", "FINAL", "THIRD_PLACE")]
    korows = [{"stage": m["stage"], "home": cz(m["homeTeam"]["name"] or ""),
               "away": cz(m["awayTeam"]["name"] or "")} for m in ko
              if m["homeTeam"]["name"] and m["awayTeam"]["name"]]
    if korows:
        p3 = os.path.join(ROOT, "data_user", "ko_real_2026.csv")
        with open(p3, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["stage", "home", "away"])
            w.writeheader(); w.writerows(korows)
        print(f"OK -> {p3} ({len(korows)} cruces reales de eliminatorias)")


if __name__ == "__main__":
    main()
