"""Reconstrucción de la fase de grupos del Mundial 2026 a partir de los datos.

Como el dataset ya contiene los 72 partidos de grupos (con resultados reales),
reconstruimos los 12 grupos, las tablas de posiciones, y los clasificados
(1º y 2º de cada grupo + los 8 mejores terceros) para sembrar las eliminatorias.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from data_prep import get_wc2026_groupstage, load_results, build_alias_map

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "wc2026_groups.json")


def load_official_groups() -> dict:
    """Grupos oficiales (letras correctas) desde config/wc2026_groups.json.

    Normaliza los nombres con el mismo alias map que los resultados.
    """
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    aliases = build_alias_map()
    groups = {}
    for letter, teams in data["groups"].items():
        groups[letter] = sorted(aliases.get(t, t) for t in teams)
    return groups


def reconstruct_groups(wc: pd.DataFrame) -> dict:
    """Devuelve dict {grupo_letra: [equipos]} reconstruido por componentes.

    En fase de grupos solo se enfrentan equipos del mismo grupo, así que los
    grupos son los componentes conexos del grafo "jugó contra".
    """
    # Construir adyacencia
    adj: dict[str, set] = {}
    first_seen: dict[str, pd.Timestamp] = {}
    for _, row in wc.iterrows():
        h, a, d = row["home_team"], row["away_team"], row["date"]
        adj.setdefault(h, set()).add(a)
        adj.setdefault(a, set()).add(h)
        first_seen.setdefault(h, d)
        first_seen.setdefault(a, d)

    visited = set()
    components = []
    for team in adj:
        if team in visited:
            continue
        stack = [team]
        comp = set()
        while stack:
            t = stack.pop()
            if t in visited:
                continue
            visited.add(t)
            comp.add(t)
            stack.extend(adj[t] - visited)
        components.append(comp)

    # Ordenar grupos por la fecha del primer partido del componente -> letra A,B,...
    def comp_first_date(comp):
        return min(first_seen[t] for t in comp)

    components.sort(key=comp_first_date)
    groups = {}
    for i, comp in enumerate(components):
        letter = chr(ord("A") + i)
        groups[letter] = sorted(comp)
    return groups


def compute_standings(wc: pd.DataFrame, groups: dict) -> dict:
    """Tabla de posiciones por grupo aplicando criterios FIFA (pts, DG, GF, H2H)."""
    team_to_group = {t: g for g, teams in groups.items() for t in teams}

    stats = {
        t: {"team": t, "group": team_to_group[t], "P": 0, "W": 0, "D": 0, "L": 0,
            "GF": 0, "GA": 0, "GD": 0, "Pts": 0}
        for t in team_to_group
    }
    # Resultados head-to-head para desempate
    h2h_pts: dict[tuple, int] = {}

    for _, row in wc.iterrows():
        h, a = row["home_team"], row["away_team"]
        hs, as_ = int(row["home_score"]), int(row["away_score"])
        stats[h]["P"] += 1; stats[a]["P"] += 1
        stats[h]["GF"] += hs; stats[h]["GA"] += as_
        stats[a]["GF"] += as_; stats[a]["GA"] += hs
        if hs > as_:
            stats[h]["W"] += 1; stats[a]["L"] += 1
            stats[h]["Pts"] += 3
            h2h_pts[(h, a)] = h2h_pts.get((h, a), 0) + 3
        elif hs < as_:
            stats[a]["W"] += 1; stats[h]["L"] += 1
            stats[a]["Pts"] += 3
            h2h_pts[(a, h)] = h2h_pts.get((a, h), 0) + 3
        else:
            stats[h]["D"] += 1; stats[a]["D"] += 1
            stats[h]["Pts"] += 1; stats[a]["Pts"] += 1
            h2h_pts[(h, a)] = h2h_pts.get((h, a), 0) + 1
            h2h_pts[(a, h)] = h2h_pts.get((a, h), 0) + 1

    for t in stats:
        stats[t]["GD"] = stats[t]["GF"] - stats[t]["GA"]

    def sort_group(teams):
        # Orden principal: Pts, GD, GF; luego head-to-head pts entre empatados
        def key(t):
            return (stats[t]["Pts"], stats[t]["GD"], stats[t]["GF"])
        teams_sorted = sorted(teams, key=key, reverse=True)
        # Desempate H2H simple para pares con misma key
        i = 0
        while i < len(teams_sorted) - 1:
            j = i
            while (j + 1 < len(teams_sorted)
                   and key(teams_sorted[j + 1]) == key(teams_sorted[i])):
                j += 1
            if j > i:
                tied = teams_sorted[i:j + 1]
                tied.sort(key=lambda t: sum(h2h_pts.get((t, o), 0) for o in tied
                                            if o != t), reverse=True)
                teams_sorted[i:j + 1] = tied
            i = j + 1
        return teams_sorted

    standings = {}
    for g, teams in groups.items():
        ordered = sort_group(teams)
        rows = []
        for pos, t in enumerate(ordered, start=1):
            r = dict(stats[t]); r["pos"] = pos
            rows.append(r)
        standings[g] = rows
    return standings


def qualifiers(standings: dict) -> dict:
    """Devuelve clasificados: ganadores, segundos y 8 mejores terceros."""
    winners = {}
    runners = {}
    thirds = []
    for g, rows in standings.items():
        winners[g] = rows[0]
        runners[g] = rows[1]
        thirds.append(rows[2])
    # Mejores terceros: Pts, GD, GF
    thirds.sort(key=lambda r: (r["Pts"], r["GD"], r["GF"]), reverse=True)
    best_thirds = thirds[:8]
    return {
        "winners": winners,
        "runners": runners,
        "best_thirds": best_thirds,
        "all_thirds": thirds,
    }


if __name__ == "__main__":
    wc = get_wc2026_groupstage(load_results())
    groups = reconstruct_groups(wc)
    print(f"Grupos reconstruidos: {len(groups)}")
    for g, teams in groups.items():
        print(f"  Grupo {g}: {teams}")
    standings = compute_standings(wc, groups)
    print("\n=== TABLAS ===")
    for g, rows in standings.items():
        print(f"\nGrupo {g}")
        for r in rows:
            print(f"  {r['pos']}. {r['team']:<22} "
                  f"Pts={r['Pts']} DG={r['GD']:+d} GF={r['GF']}")
    q = qualifiers(standings)
    print("\n=== MEJORES TERCEROS (8 clasifican) ===")
    for i, r in enumerate(q["all_thirds"], 1):
        mark = "✔" if i <= 8 else "�’"
        print(f"  {mark} {r['team']:<22} (Grupo {r['group']}) "
              f"Pts={r['Pts']} DG={r['GD']:+d} GF={r['GF']}")
