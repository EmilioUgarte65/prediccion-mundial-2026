"""Intenta bajar stats de jugador del Mundial 2026 desde FBref (soccerdata)."""
import os
import soccerdata as sd

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                   "data_user", "fbref_players_2026.csv")

# soccerdata usa "INT-World Cup" como clave de liga del Mundial
for league in ("INT-World Cup", "FIFA World Cup"):
    try:
        print(f"Probando league='{league}', season='2026'...")
        fb = sd.FBref(leagues=league, seasons="2026")
        df = fb.read_player_season_stats(stat_type="standard")
        df = df.reset_index()
        # aplanar columnas MultiIndex -> "Bloque_Sub" (ej. Performance_Gls)
        flat = []
        for c in df.columns:
            if isinstance(c, tuple):
                parts = [str(x) for x in c if str(x) and "Unnamed" not in str(x)]
                flat.append("_".join(parts))
            else:
                flat.append(str(c))
        df.columns = flat
        df.to_csv(OUT, index=False, encoding="utf-8")
        print(f"OK -> {OUT}  ({len(df)} jugadores)")
        print("Columnas:", list(df.columns))
        break
    except Exception as e:  # noqa: BLE001
        print(f"  ! falló con '{league}': {e}")
