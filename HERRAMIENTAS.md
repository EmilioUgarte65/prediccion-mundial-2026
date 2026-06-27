# Toolkit de recopilación de datos

Herramientas para **recolectar y cachear** datos. Regla de oro: las APIs se
llaman SOLO aquí (en `src/fetch_*` / `src/build_*`), se guardan en `data_user/`,
y `build.py` lee **solo de esos archivos** → el pipeline no consume cuota.

Orquestador: **`python fetch_all.py`** (baja lo que falte) · `--force` (re-baja todo).

## Recolectores (cada uno guarda en data_user/)

| Herramienta | Fuente | Clave | Qué baja | Archivo |
|---|---|---|---|---|
| `src/fetch_squads.py` | Football-Data.org | sí (free) | 48 planteles (1249 jugadores) | `squads_2026.csv` |
| `src/fetch_odds.py` | The Odds API | sí (free) | cuotas 1X2 (refrescable) | `odds.csv` |
| `src/fetch_weather.py` | Open-Meteo | **no** | clima por sede | `weather.csv` |
| `src/fetch_statsbomb_full.py` | StatsBomb (GitHub) | **no** | xG, tarjetas, faltas 2018/22 | `sb_match_stats.csv`, `sb_cards_detail.csv` |
| `src/build_player_trajectory.py` | local (cruce) | — | trayectoria goleadora x jugador | `player_trajectory.csv` |
| (manual) FootyStats | navegador | — | xG por equipo | `team_xg.csv` |
| repo de datos | martj42 (git) | **no** | resultados/goleadores | `data_repo/` |

## Cómo refrescar antes de una jornada
```powershell
cd data_repo; git pull; cd ..     # resultados nuevos
python fetch_all.py               # cuotas + clima + lo que falte
python build.py                   # re-predice (cero API)
```

## ⚠️ Lo que NO se puede scrapear (honesto)
Estos **bloquean bots (403) o lo prohíben sus ToS** — no construyo scrapers para ellos:
- **FBref, Sofascore, WhoScored, Transfermarkt, SoFIFA** → para sus datos (xG por
  partido 2026, stats por jugador, formaciones, lesiones en vivo) se necesita una
  **API de pago** (Sofascore/SportMonks/Opta) o exportar a mano.

"Todo está en internet", sí — pero gran parte está **protegido o bloqueado**.
Lo que es **abierto/API** ya lo recolectamos y cacheamos aquí.
