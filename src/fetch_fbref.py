"""Colector robusto de xG + tiros + balón parado por partido desde FBref (soccerdata).

Usa read_team_match_stats y detecta automáticamente las columnas de xG/tiros/
córners (maneja MultiIndex). Guarda data_user/fbref_team_match.csv (una fila por
equipo-partido). FBref usa datos Opta -> calidad profesional, gratis.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "fbref_team_match.csv")
SEASONS = ["2018", "2022"]


def _flat(cols):
    out = []
    for c in cols:
        if isinstance(c, tuple):
            out.append("_".join(str(x) for x in c if str(x) and "Unnamed" not in str(x)))
        else:
            out.append(str(c))
    return out


def main():
    import soccerdata as sd
    import pandas as pd

    frames = []
    for s in SEASONS:
        fb = sd.FBref(leagues="INT-World Cup", seasons=s)
        try:
            df = fb.read_team_match_stats(stat_type="schedule")
        except Exception as e:  # noqa: BLE001
            print(f"  ! WC {s}: {e}"); continue
        df = df.reset_index()
        df.columns = _flat(df.columns)
        cols = {c.lower(): c for c in df.columns}
        xg = next((cols[c] for c in cols if c == "xg" or c.endswith("_xg")), None)
        print(f"  WC {s}: {len(df)} filas. xG col -> {xg}")
        df["season"] = s
        frames.append(df)
    if not frames:
        print("Sin datos FBref."); return
    out = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"OK -> {OUT}  ({len(out)} filas, {len(out.columns)} columnas)")
    print("Columnas:", list(out.columns)[:25])


if __name__ == "__main__":
    main()
