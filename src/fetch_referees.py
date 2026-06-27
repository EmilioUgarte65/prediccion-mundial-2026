"""#4 — Árbitros del Mundial 2026 (FBref vía soccerdata).

Baja el calendario del torneo y extrae el árbitro asignado a cada partido.
NOTA: antes del torneo FBref suele NO tener árbitros asignados -> saldrá vacío;
correrlo de nuevo cuando se publiquen. Guarda data_user/referees_2026.csv.
"""
from __future__ import annotations

import os

import soccerdata as sd

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, "data_user", "referees_2026.csv")


def main():
    fb = None
    for lg in ("INT-World Cup", "FIFA World Cup"):
        try:
            fb = sd.FBref(leagues=lg, seasons="2026")
            sched = fb.read_schedule()
            print(f"Liga OK: {lg}  ({len(sched)} partidos)")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  ! {lg}: {e}"); fb = None
    if fb is None:
        print("No se pudo leer el calendario."); return

    cols = [c for c in sched.columns if str(c).lower() in
            ("referee", "home_team", "away_team", "date", "game")]
    ref = sched[cols].copy() if cols else sched.copy()
    ref.to_csv(OUT, encoding="utf-8")
    refs = sched["referee"].dropna().unique() if "referee" in sched.columns else []
    print(f"OK -> {OUT}  | árbitros asignados: {len(refs)}")
    if len(refs) == 0:
        print("  (vacío: FBref aún no publica árbitros; reintentar cerca del torneo)")


if __name__ == "__main__":
    main()
