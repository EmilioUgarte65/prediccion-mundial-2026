"""Descarga TODAS las métricas de jugador del Mundial 2026 desde FBref (8 categorías)."""
import os
import soccerdata as sd
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                   "data_user", "fbref_masivo_2026.csv")
CATS = ["standard", "shooting", "passing", "passing_types", "gca",
        "defense", "possession", "misc"]


def main():
    fb = None
    for lg in ("INT-World Cup", "FIFA World Cup"):
        try:
            fb = sd.FBref(leagues=lg, seasons="2026")
            fb.read_player_season_stats(stat_type="standard")  # prueba
            print(f"Liga OK: {lg}"); break
        except Exception as e:  # noqa: BLE001
            print(f"  ! {lg}: {e}"); fb = None
    if fb is None:
        print("No se pudo conectar a FBref."); return

    frames = []
    for cat in CATS:
        try:
            df = fb.read_player_season_stats(stat_type=cat)
            df.columns = ["_".join([str(x) for x in col if str(x)]).strip()
                          for col in df.columns.values]
            frames.append(df)
            print(f"  {cat}: {df.shape[1]} columnas")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {cat}: {e}")
    if not frames:
        print("Sin datos."); return
    big = pd.concat(frames, axis=1)
    big = big.loc[:, ~big.columns.duplicated()]
    big.to_csv(OUT, encoding="utf-8")
    print(f"\nOK -> {OUT}  ({big.shape[0]} jugadores, {big.shape[1]} métricas)")


if __name__ == "__main__":
    main()
