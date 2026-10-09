# Predicción Mundial 2026 — XGBoost + Ratings

Modelo predictivo del **Mundial 2026** que combina **ratings (Elo + ataque/defensa)**
con **XGBoost**, modela **los minutos en que caen los goles** y simula las
**eliminatorias** (cómo van pasando las fases). El resultado se muestra en una
**página web** estilo Mundial: cuadro de eliminatorias, y dentro de cada partido
la predicción del marcador, los minutos de gol y cómo va quedando.

> La fase de grupos ya se jugó (los resultados reales están en los datos), así que
> el modelo **predice desde la Ronda de 32 hasta la final**.

## Cómo funciona

| Componente | Archivo | Qué hace |
|---|---|---|
| Datos | `src/data_prep.py` | Carga y limpia `results`, `goalscorers`, `shootouts`; normaliza nombres históricos. |
| Grupos | `src/wc2026.py` + `config/wc2026_groups.json` | Grupos oficiales, tablas reales y clasificados (1º, 2º y 8 mejores terceros). |
| Ratings | `src/ratings.py` | **Elo** dinámico (margen de gol + localía + peso de torneo) y **ataque/defensa** por regresión de Poisson con decaimiento temporal. |
| Modelo | `src/model.py` | **XGBoost**: clasificador de resultado (validación) y dos regresores Poisson de goles (motor de la simulación), usando Elo + ataque/defensa + forma reciente. |
| Tiempos de gol | `src/goal_timing.py` | Distribución empírica del minuto de gol (los goles tardíos son más probables). |
| Cuadro | `src/bracket.py` | Estructura **oficial** R32→Final + asignación de los 8 terceros a sus slots. |
| Simulación | `src/simulate.py` | **Monte Carlo**: probabilidades por partido, marcador representativo, línea de tiempo de goles y probabilidad de avance por fase. |
| Web | `web/` | Página oscura estilo Mundial: bracket + grupos + favoritos + modal por partido. |

## Uso

```bash
# 1. (una vez) clonar los datos dentro del proyecto
git clone https://github.com/martj42/international_results.git data_repo

# 2. instalar dependencias
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # Linux/Mac

# 3. entrenar + simular -> genera web/data/predictions.json
.venv\Scripts\python build.py

# 4. ver la web
.venv\Scripts\python -m http.server 8000 --directory web
# abrir http://localhost:8000
```

## La página web

- **Camino al título**: cuadro de eliminatorias con el escenario más probable
  (avanza el favorito de cada cruce). Clic en un partido para ver el detalle.
- **Detalle de partido** (modal): probabilidad de avanzar, marcador previsto,
  **línea de tiempo de goles** (minuto + cómo va quedando) y un mapa de calor de
  **en qué tramo es más probable que anote cada equipo**.
- **Grupos**: posiciones finales reales con los clasificados resaltados.
- **Favoritos**: probabilidad de cada selección de alcanzar cada fase y de ser campeón.

## Notas de modelado

- El **Elo** se calcula sobre toda la historia (>49k partidos) y refleja la fuerza
  actual de cada selección.
- Los **goles esperados** salen de los regresores Poisson de XGBoost; la
  simulación muestrea marcadores y, en eliminatoria, resuelve empates con
  **prórroga** y **penales** (probabilidad por Elo).
- Los **minutos de gol** se muestrean de la distribución empírica real de
  `goalscorers.csv`.
- Los grupos y las letras oficiales viven en `config/wc2026_groups.json`
  (editable). El cuadro de terceros respeta las restricciones de grupo de la FIFA.

Datos: [martj42/international_results](https://github.com/martj42/international_results).
Diseño guiado por la skill UI/UX Pro Max (tema oscuro, Fira Code/Fira Sans).

## Instalar en otra PC

### Requisitos

- **Python 3.11 o superior** (probado con Python 3.14.2) y **Git**.
- Navegador moderno para ver `web/`.
- Opcional: **Docker** (solo para `src/fetch_market_values.py`, ver abajo) y **Google Chrome**
  (solo para los recolectores de FBref con `soccerdata`).

### Pasos (Windows)

```powershell
git clone https://github.com/EmilioUgarte65/prediccion-mundial-2026.git
cd prediccion-mundial-2026
powershell -ExecutionPolicy Bypass -File .\instalar.ps1     # .venv + requirements.txt + data_repo/
.venv\Scripts\python build.py                               # regenera web/data/predictions.json
.venv\Scripts\python -m http.server 8000 --directory web    # abrir http://localhost:8000
```

`instalar.ps1 -Opcional` instala además `requirements-opcional.txt` (soccerdata, para FBref).
En Linux/Mac: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` y clonar
`data_repo/` a mano (paso 1 de *Uso*).

Si solo quieres **ver** la web, no hace falta instalar nada: `web/data/` ya trae las predicciones
generadas; basta con servir la carpeta `web/`.

### Configuración (llaves de API)

Las llaves van en `config/api_keys.json`, que **no** se sube al repo. Copia la plantilla
`config/api_keys.example.json` y llena solo las que uses. `build.py` no usa ninguna: solo hacen
falta para refrescar datos con `fetch_all.py` y `src/fetch_*.py`.

| Llave | Servicio | Uso |
|---|---|---|
| `football_data_org` | https://www.football-data.org (gratis con registro) | planteles y resultados en vivo |
| `the_odds_api` | https://the-odds-api.com (plan gratis) | cuotas 1X2 y de campeón |
| `rapidapi` | https://rapidapi.com (API-Football) | alineaciones (`src/fetch_lineups.py`) |
| `api_football` | https://www.api-football.com | no la usa ningún script actual (puede quedar vacía) |

Sin variables de entorno obligatorias. `actualizar.ps1` (actualización nocturna) usa la carpeta
donde está el propio script, así que funciona en cualquier ruta; se puede programar con el
Programador de tareas de Windows.

### Datos que no están en el repo

- `data_repo/`: resultados históricos de selecciones; se clona de
  https://github.com/martj42/international_results (lo hace `instalar.ps1`).
- `backups/`: respaldos locales de modelos; no hacen falta.
- `skill_uiux/`: material de diseño usado durante el desarrollo; no hace falta.
- `data_user/` sí está en el repo (datos ya cacheados), así que `build.py` funciona sin APIs.
- Valor de mercado (opcional): `docker compose -f docker/transfermarkt-compose.yml up -d`
  levanta la API de Transfermarkt en `http://localhost:8011`.

### Problemas comunes

- `build.py` falla por archivos de `data_repo/`: falta clonar el repositorio de datos.
- Error `KeyError`/`FileNotFoundError` en un `fetch_*.py`: falta `config/api_keys.json` o la llave.
- Acentos raros en consola de Windows: `set PYTHONUTF8=1` (lo hace `actualizar.ps1`).
- Puerto 8000 ocupado: usa otro, p. ej. `-m http.server 8080 --directory web`.
