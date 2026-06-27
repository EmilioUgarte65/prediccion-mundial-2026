"""Descarga y CACHEA toda la data externa una sola vez (ahorra cuota de APIs).

Cada fuente se guarda en data_user/ y el pipeline (build.py) lee SOLO de esos
archivos locales -> build.py NUNCA consume API. Vuelve a correr esto solo cuando
quieras refrescar (p. ej. cuotas antes de cada jornada).

Uso:
    python fetch_all.py            # baja lo que falte (no re-baja lo estático)
    python fetch_all.py --force    # vuelve a bajar todo
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
DU = os.path.join(os.path.dirname(__file__), "data_user")

FORCE = "--force" in sys.argv


def have(name):
    return os.path.exists(os.path.join(DU, name))


def step(label, fn, cache_file, always=False):
    if not FORCE and not always and cache_file and have(cache_file):
        print(f"[cache] {label}: ya existe ({cache_file}), se omite.")
        return
    print(f"[bajar] {label}...")
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"   ! fallo {label}: {e}")


def main():
    # Estáticos (no cambian) -> solo si faltan
    import fetch_squads
    step("Planteles 2026 (Football-Data.org)", fetch_squads.main, "squads_2026.csv")

    import fetch_statsbomb_full
    step("xG + tarjetas + faltas (StatsBomb 2018/22)", fetch_statsbomb_full.main,
         "sb_match_stats.csv")

    import build_player_trajectory
    step("Trayectoria por jugador (cache local)", build_player_trajectory.main,
         "player_trajectory.csv")

    # Dinámicos (cambian) -> siempre se refrescan
    import fetch_odds
    step("Cuotas de mercado (The Odds API)", fetch_odds.main, None, always=True)

    import fetch_weather
    step("Clima por sede (Open-Meteo, gratis)", fetch_weather.main, None, always=True)

    print("\nListo. Ahora corre:  python build.py   (lee solo de data_user/, sin API)")


if __name__ == "__main__":
    main()
