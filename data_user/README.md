# Cómo darme tus datos para mejorar la exactitud

Llena cualquiera de estos archivos (NO hace falta llenarlos todos) y avísame.
Yo los conecto al modelo y mido en el backtest cuánto sube el acierto.

## Reglas generales
- **Formato:** CSV separado por comas, codificación UTF-8 (Excel: "Guardar como CSV UTF-8").
- **Fechas:** siempre `AAAA-MM-DD` (ej. `2026-06-26`).
- **Nombres de equipos:** deben coincidir con los del dataset. Ojo con estos:
  `United States`, `Czech Republic`, `Ivory Coast`, `DR Congo`, `South Korea`,
  `Curaçao`, `Cape Verde`, `Saudi Arabia`, `Bosnia and Herzegovina`, `New Zealand`.
- No cambies los nombres de las columnas (los encabezados). Sí puedes borrar las filas de ejemplo.
- Puedes llenar solo algunos partidos/jugadores; lo parcial igual ayuda.

## Archivos (de mayor a menor impacto)

### 1. `xg_matches.csv`  ← lo que MÁS sube la exactitud
Goles esperados (xG) por partido. Una fila por partido jugado.
`date, home_team, away_team, home_xg, away_xg`  (xG con decimales, ej. 2.8)
> Fuente típica: FBref, Understat, SofaScore, StatsBomb.

### 2. `odds.csv`  ← gran salto en calibración
Cuotas decimales (idealmente las de cierre, ej. Pinnacle/Bet365).
`date, home_team, away_team, odd_home, odd_draw, odd_away`  (ej. 1.85, 3.60, 4.20)

### 3. `players.csv`  ← fuerza de plantel
Jugadores clave por selección.
`team, player, rating, market_value_eur, position, available`
- `rating`: 0-100 (estilo FIFA). Si no tienes, déjalo vacío.
- `market_value_eur`: valor de mercado en euros (Transfermarkt). Opcional.
- `available`: 1 si juega el Mundial, 0 si está lesionado/fuera.

### 4. `availability.csv`  ← bajas/lesiones por partido
Qué tan completo llega cada equipo a cada partido.
`date, team, strength_pct, notes`
- `strength_pct`: 100 = plantel completo; 85 = sin un par de titulares, etc.

## Cómo entregármelos
Cualquiera de estas:
1. **Llenar estos CSV** y decirme "ya están" (yo los leo de `data_user/`).
2. **Pegar los datos** aquí en el chat (aunque sea una tabla).
3. **Pasarme un link** (Kaggle, FBref, una hoja de Google, etc.) y yo los bajo/armo.
