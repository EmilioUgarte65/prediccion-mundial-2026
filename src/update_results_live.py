"""Actualiza data_repo/results.csv con los resultados REALES más recientes del
Mundial 2026 desde football-data.org (rellena los marcadores que falten).

Cruza por el par de equipos (normalizado, sin importar orden ni fecha exacta).
"""
from __future__ import annotations

import json
import os
import unicodedata
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
CSV = os.path.join(ROOT, "data_repo", "results.csv")
KEY = json.load(open(os.path.join(ROOT, "config", "api_keys.json"),
                    encoding="utf-8"))["football_data_org"]

ALIAS = {
    "cape verde islands": "cape verde", "cabo verde": "cape verde",
    "turkiye": "turkey", "ivory coast": "ivory coast",
    "cote divoire": "ivory coast", "korea republic": "south korea",
    "ir iran": "iran", "ipr korea": "north korea", "czechia": "czech republic",
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().strip().replace("islands", "").strip()
    return ALIAS.get(s, s)


def main():
    j = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.football-data.org/v4/competitions/WC/matches",
        headers={"X-Auth-Token": KEY}), timeout=30))
    fin = [m for m in j["matches"] if m["status"] == "FINISHED"]
    print(f"football-data: {len(fin)} partidos finalizados")

    df = pd.read_csv(CSV)
    d = pd.to_datetime(df["date"], errors="coerce")
    wc = (df["tournament"] == "FIFA World Cup") & (d >= pd.Timestamp("2026-01-01"))
    idxs = df.index[wc].tolist()
    # índice por par de equipos normalizado
    pair_rows = {}
    for i in idxs:
        key = frozenset((norm(df.at[i, "home_team"]), norm(df.at[i, "away_team"])))
        pair_rows.setdefault(key, []).append(i)

    updated = added = unmatched = 0
    miss = []
    for m in fin:
        h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
        ft = m["score"]["fullTime"]
        if ft["home"] is None:
            continue
        key = frozenset((norm(h), norm(a)))
        rows = pair_rows.get(key, [])
        if not rows:
            unmatched += 1; miss.append(f"{h} vs {a}"); continue
        # elegir la fila correcta: la de fecha más cercana al partido real
        # (evita asignar el marcador al partido equivocado si el par se repite)
        fd = pd.to_datetime(m.get("utcDate", ""), errors="coerce")
        if pd.notna(fd) and len(rows) > 1:
            i = min(rows, key=lambda k: abs((pd.to_datetime(df.at[k, "date"],
                    errors="coerce") - fd).days if pd.notna(pd.to_datetime(
                    df.at[k, "date"], errors="coerce")) else 9999))
        else:
            i = rows[0]
        # orientar el marcador según cómo está el partido en el CSV
        if norm(df.at[i, "home_team"]) == norm(h):
            hs, as_ = ft["home"], ft["away"]
        else:
            hs, as_ = ft["away"], ft["home"]
        cur = pd.to_numeric(pd.Series([df.at[i, "home_score"]]), errors="coerce")[0]
        if pd.isna(cur):
            updated += 1
        df.at[i, "home_score"] = hs
        df.at[i, "away_score"] = as_

    df.to_csv(CSV, index=False)
    print(f"Rellenados (antes NA): {updated} | sin match: {unmatched}")
    if miss:
        print("  no cruzaron:", miss[:10])
    # estado final
    hs = pd.to_numeric(df.loc[wc, "home_score"], errors="coerce")
    print(f"WC2026 con marcador ahora: {int(hs.notna().sum())}")


if __name__ == "__main__":
    main()
