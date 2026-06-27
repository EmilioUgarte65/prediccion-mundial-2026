"""Recolector de CLIMA por sede del Mundial 2026 (Open-Meteo, gratis, sin API key).

Para cada sede (coordenadas en geo.py) baja el pronóstico de los próximos días
(temperatura máx/mín y lluvia) y lo guarda en data_user/weather.csv.
Open-Meteo es gratuito y no requiere clave ni viola ToS.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request

import geo

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "weather.csv")


def get(url):
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.load(r)


def main():
    rows = []
    for city, (lat, lon, alt) in geo.VENUES.items():
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
               f"&forecast_days=10&timezone=auto")
        try:
            d = get(url)
            daily = d.get("daily", {})
            for i, day in enumerate(daily.get("time", [])):
                rows.append({
                    "city": city, "date": day, "altitude": alt,
                    "tmax": daily["temperature_2m_max"][i],
                    "tmin": daily["temperature_2m_min"][i],
                    "rain_mm": daily["precipitation_sum"][i],
                })
        except Exception as e:  # noqa: BLE001
            print(f"  ! {city}: {e}")
    if not rows:
        print("Sin datos de clima."); return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"OK -> {OUT}  ({len(rows)} días-sede)")


if __name__ == "__main__":
    main()
