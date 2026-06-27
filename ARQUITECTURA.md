# Arquitectura: qué dato alimenta a qué modelo

Tres niveles. Cada dato está donde **sí aporta** (predictor, ajuste forward, o info).

## 1) Modelos ENTRENADOS (se validan en backtest, 56.5% en 15 Mundiales)
Usan datos que existen en los **49,000 partidos** de historia:
- **Predictivo (XGBoost)** — clasificador 1X2 + 2 regresores Poisson de goles.
- **Estadístico (Dixon-Coles)** — distribución de marcadores con corrección de bajos.
- **Elo** — ratings dinámicos.
- **Ensemble** — combina Elo + Estadístico + XGBoost (pesos tuneados en dev).

**Features:** Elo, ataque/defensa, forma reciente, neutral/localía, peso del torneo, geo (altitud/viajes). *(Probados y descartados por no mejorar: penales, H2H.)*

## 2) Motor FORWARD 2026 (ajustes sobre la λ; no backtesteable sin fuga)
Solo aplican a partidos futuros de 2026 (son info pre-partido legítima):
| Dato | Efecto |
|---|---|
| xG externo (FootyStats) | mezcla con la λ del modelo |
| **Lesiones / disponibilidad** | baja ataque si falta crack; sube rival si faltan defensas |
| **Ánimo / NLP (noticias)** | ±5% por confianza |
| **Fatiga de veteranos** | pequeña merma |
| **Bottom-up jugadores** (FBref minutos+xG) | ataque del equipo desde sus jugadores reales |
| Ventaja de anfitrión | +12% gol local (Méx/EEUU/Can) |
| Cuotas de partido (mercado) | señal líder del 1X2 |
| Cuotas de campeón | prior del torneo (Favoritos: Modelo vs Mercado) |
| Calibración de goles | ×1.06 (2026 es goleador) |
| Rojas | eventos en la simulación |

## 3) Solo INFORMACIÓN (no entran a ningún predictor)
Tarjetas, córners, dependencia de penal, goleadores/trayectoria, stats FBref por
jugador, **pedigrí StatsBomb 2018/22**, clima, stats del torneo. *(Se muestran en
la web; probados como feature no suben el acierto o cubren <15%.)*

## Por qué no "todo en todos"
1. Una feature debe existir en **todas** las filas de entrenamiento; los datos ricos
   (xG, lesiones, jugador) solo existen para 2026/2018-22 → no se puede entrenar con
   ellos → se aplican como **ajuste forward**.
2. Lo que se probó como feature y no mejoró (regularización + CV lo confirma) → queda
   como **información**, no como predictor (evita ruido).

## Fuentes de datos
martj42 (resultados/goles, todo el histórico) · FootyStats (xG equipo) ·
The Odds API (cuotas) · Football-Data.org (planteles/árbitros) · Open-Meteo (clima) ·
StatsBomb (xG/tarjetas/pedigrí 2018-22) · FBref vía soccerdata (stats jugador 2026).
