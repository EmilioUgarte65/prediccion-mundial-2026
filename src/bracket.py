"""Cuadro de eliminatorias oficial del Mundial 2026 (Ronda de 32 -> Final).

Estructura oficial de partidos (slots por posición de grupo) y asignación de los
8 mejores terceros a sus slots respetando las restricciones de grupo de la FIFA.
"""
from __future__ import annotations

# slot: ("W", grupo) ganador | ("R", grupo) segundo | ("T", set_grupos) tercero
R32_STRUCTURE = {
    73: (("R", "A"), ("R", "B")),
    74: (("W", "E"), ("T", {"A", "B", "C", "D", "F"})),
    75: (("W", "F"), ("R", "C")),
    76: (("W", "C"), ("R", "F")),
    77: (("W", "I"), ("T", {"C", "D", "F", "G", "H"})),
    78: (("R", "E"), ("R", "I")),
    79: (("W", "A"), ("T", {"C", "E", "F", "H", "I"})),
    80: (("W", "L"), ("T", {"E", "H", "I", "J", "K"})),
    81: (("W", "D"), ("T", {"B", "E", "F", "I", "J"})),
    82: (("W", "G"), ("T", {"A", "E", "H", "I", "J"})),
    83: (("R", "K"), ("R", "L")),
    84: (("W", "H"), ("R", "J")),
    85: (("W", "B"), ("T", {"E", "F", "G", "I", "J"})),
    86: (("W", "J"), ("R", "H")),
    87: (("W", "K"), ("T", {"D", "E", "I", "J", "L"})),
    88: (("R", "D"), ("R", "G")),
}

R16_FEED = {
    89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
}
QF_FEED = {97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96)}
SF_FEED = {101: (97, 98), 102: (99, 100)}
FINAL_FEED = {104: (101, 102)}
THIRD_PLACE_FEED = {103: (101, 102)}  # perdedores de semifinales

ROUND_OF = {
    "R32": list(R32_STRUCTURE.keys()),
    "R16": list(R16_FEED.keys()),
    "QF": list(QF_FEED.keys()),
    "SF": list(SF_FEED.keys()),
    "Final": list(FINAL_FEED.keys()),
}


def assign_thirds(best_thirds: list) -> dict:
    """Asigna los 8 mejores terceros a los slots T respetando restricciones.

    best_thirds: lista de dicts (ya ordenada por ranking) con clave 'group'.
    Devuelve {match_id: group_letter_del_tercero}.
    """
    third_slots = [(m, slots) for m, struct in R32_STRUCTURE.items()
                   for slots in [struct]
                   for s in struct if s[0] == "T"]
    # match_id -> set permitido
    slots = {}
    for m, struct in R32_STRUCTURE.items():
        for s in struct:
            if s[0] == "T":
                slots[m] = s[1]
    slot_ids = sorted(slots.keys())

    groups_by_rank = [t["group"] for t in best_thirds]  # mejor -> peor
    qualifying = set(groups_by_rank)

    assignment: dict[int, str] = {}
    used = set()

    def backtrack(idx: int) -> bool:
        if idx == len(slot_ids):
            return True
        m = slot_ids[idx]
        allowed = slots[m] & qualifying
        # candidatos ordenados por ranking (mejor tercero primero)
        for g in groups_by_rank:
            if g in allowed and g not in used:
                used.add(g)
                assignment[m] = g
                if backtrack(idx + 1):
                    return True
                used.remove(g)
                del assignment[m]
        return False

    if not backtrack(0):
        raise RuntimeError("No existe asignación válida de terceros "
                           f"para los grupos {sorted(qualifying)}")
    return assignment


def resolve_r32_teams(qual: dict) -> dict:
    """Devuelve {match_id: (teamA, teamB)} para la Ronda de 32."""
    winners = {g: r["team"] for g, r in qual["winners"].items()}
    runners = {g: r["team"] for g, r in qual["runners"].items()}
    third_by_group = {t["group"]: t["team"] for t in qual["best_thirds"]}
    third_assign = assign_thirds(qual["best_thirds"])

    def team_of(slot, match_id):
        kind, val = slot
        if kind == "W":
            return winners[val]
        if kind == "R":
            return runners[val]
        if kind == "T":
            return third_by_group[third_assign[match_id]]
        raise ValueError(slot)

    matches = {}
    for m, (sa, sb) in R32_STRUCTURE.items():
        matches[m] = (team_of(sa, m), team_of(sb, m))
    return matches, third_assign


if __name__ == "__main__":
    from data_prep import get_wc2026_groupstage, load_results
    from wc2026 import load_official_groups, compute_standings, qualifiers

    wc = get_wc2026_groupstage(load_results())
    groups = load_official_groups()
    standings = compute_standings(wc, groups)
    qual = qualifiers(standings)
    matches, third_assign = resolve_r32_teams(qual)
    print("=== Asignacion de terceros (match -> grupo) ===")
    for m, g in sorted(third_assign.items()):
        print(f"  Match {m}: 3o Grupo {g}")
    print("\n=== RONDA DE 32 ===")
    for m in sorted(matches):
        a, b = matches[m]
        print(f"  Match {m}: {a} vs {b}")
