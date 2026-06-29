"""Búsqueda automática de LESIONES del Mundial 2026 (scrape de soccer26live).

Lee la tabla de lesionados (atributos data-* limpios), la normaliza al formato
del modelo (team, player, side, status, injury) y guarda injuries_2026.csv.

Robusto: reintenta; si el sitio falla o devuelve pocos datos, CONSERVA el CSV
actual (no lo pisa con basura). Así se puede correr en cada build sin riesgo.
"""
from __future__ import annotations

import csv
import html
import os
import re
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "injuries_2026.csv")
URL = "https://soccer26live.com/world-cup-2026/injuries/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

POS2SIDE = {"forward": "att", "midfielder": "mid", "defender": "def",
            "goalkeeper": "gk"}
# nombre del sitio (minúsculas) -> nombre canónico del motor
TEAM_CANON = {
    "united states": "United States", "ivory coast": "Ivory Coast",
    "south korea": "South Korea", "dr congo": "DR Congo", "congo dr": "DR Congo",
    "czechia": "Czech Republic", "czech republic": "Czech Republic",
    "bosnia": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "cape verde": "Cape Verde", "cabo verde": "Cape Verde",
    "turkiye": "Turkey", "turkey": "Turkey",
    "korea republic": "South Korea", "usa": "United States",
    "cote d'ivoire": "Ivory Coast",
}
ROW_RE = re.compile(
    r'<tr[^>]*data-player-name="([^"]*)"[^>]*data-team-name="([^"]*)"'
    r'[^>]*data-position="([^"]*)"[^>]*data-status="([^"]*)"', re.I)
STRONG_RE = re.compile(r"<strong>([^<]+)</strong>")


def _canon_team(name):
    n = html.unescape(name).strip().lower()
    return TEAM_CANON.get(n, html.unescape(name).strip().title())


def _load_existing():
    if not os.path.exists(OUT):
        return []
    with open(OUT, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_html():
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"  intento {attempt + 1} falló: {str(e)[:60]}")
            time.sleep(3)
    return None


def main():
    doc = fetch_html()
    if not doc:
        print("No se pudo bajar el rastreador; se conserva injuries_2026.csv actual.")
        return
    # parsear filas; el <strong> da el nombre con mayúsculas/acentos
    rows = []
    for m in ROW_RE.finditer(doc):
        pname, team, pos, status = m.groups()
        if status.lower() not in ("out", "doubtful"):
            continue
        side = POS2SIDE.get(pos.lower(), "mid")
        # nombre bonito: buscar el <strong> cercano, si no, title-case
        seg = doc[m.end():m.end() + 400]
        sm = STRONG_RE.search(seg)
        disp = sm.group(1).strip() if sm else pname.title()
        disp = html.unescape(disp)
        rows.append({"team": _canon_team(team), "player": disp,
                     "side": side, "status": status.lower(), "injury": "(auto)"})
    if len(rows) < 8:
        print(f"Solo {len(rows)} lesiones parseadas (sospechoso); "
              f"se CONSERVA el CSV actual.")
        return

    # FUSIÓN: conservar lo existente (deep search manual con OUT y detalles),
    # agregar solo los lesionados nuevos que el scrape encontró.
    merged = _load_existing()
    have = {(r["team"], r["player"]) for r in merged}
    added = 0
    for r in rows:
        if (r["team"], r["player"]) not in have:
            merged.append(r); have.add((r["team"], r["player"])); added += 1
    # Filtrar a equipos que siguen vivos (clasificados a eliminatorias), si se sabe.
    ko = os.path.join(ROOT, "data_user", "ko_real_2026.csv")
    if os.path.exists(ko):
        alive = set()
        with open(ko, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                alive.add(r["home"]); alive.add(r["away"])
        if len(alive) >= 16:
            before = len(merged)
            merged = [r for r in merged if r["team"] in alive]
            if before - len(merged):
                print(f"  (filtradas {before - len(merged)} lesiones de equipos eliminados)")
    merged.sort(key=lambda r: (r["team"], r.get("status", "")))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["team", "player", "side", "status", "injury"])
        w.writeheader(); w.writerows(merged)
    nteams = len({r["team"] for r in merged})
    print(f"OK -> {OUT}  ({len(merged)} lesiones, {nteams} selecciones; "
          f"+{added} nuevas del scrape)")


if __name__ == "__main__":
    main()
