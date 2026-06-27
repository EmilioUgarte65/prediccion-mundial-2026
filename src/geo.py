"""Datos geográficos de las sedes del Mundial 2026 (calculables sin fuentes externas).

Altitud (m) y coordenadas de cada ciudad sede, para derivar:
- ventaja por altitud (CDMX/Guadalajara están en altura),
- distancia de viaje entre sedes (fatiga).
Se usa la columna 'city' de results.csv.
"""
from __future__ import annotations

import math

# ciudad -> (lat, lon, altitud_m)
VENUES = {
    # México (altura)
    "Mexico City": (19.43, -99.13, 2240),
    "Zapopan": (20.72, -103.39, 1560),       # Guadalajara
    "Guadalupe": (25.68, -100.26, 540),      # Monterrey
    # Estados Unidos
    "Inglewood": (33.95, -118.34, 30),
    "Santa Clara": (37.40, -121.97, 11),
    "Seattle": (47.59, -122.33, 56),
    "Foxborough": (42.09, -71.26, 90),
    "East Rutherford": (40.81, -74.07, 5),
    "Philadelphia": (39.90, -75.17, 12),
    "Miami Gardens": (25.96, -80.24, 3),
    "Atlanta": (33.76, -84.40, 320),
    "Arlington": (32.75, -97.09, 160),
    "Houston": (29.68, -95.41, 15),
    "Kansas City": (39.05, -94.48, 270),
    # Canadá
    "Toronto": (43.63, -79.42, 76),
    "Vancouver": (49.28, -123.11, 4),
}
DEFAULT = (39.0, -98.0, 200)  # centro de EE.UU. como respaldo


def venue(city: str):
    return VENUES.get(city, DEFAULT)


def altitude(city: str) -> float:
    return venue(city)[2]


def haversine_km(c1: str, c2: str) -> float:
    (la1, lo1, _), (la2, lo2, _) = venue(c1), venue(c2)
    r = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2 - la1)
    dlmb = math.radians(lo2 - lo1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


if __name__ == "__main__":
    print("Altitud CDMX:", altitude("Mexico City"), "m")
    print("Distancia Vancouver-Miami:", round(haversine_km("Vancouver", "Miami Gardens")), "km")
