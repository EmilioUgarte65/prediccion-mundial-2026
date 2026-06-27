# Datos que nos faltan — lista para buscar (todos los Mundiales / campeonatos)

Objetivo: cobertura para **todos los Mundiales (1930-2026)** y otros campeonatos
(Euro, Copa América, etc.). Formato ideal: **CSV con `date, home_team, away_team`**
(o `player`) para poder cruzarlo. Nombres de equipo como en martj42.

Leyenda cobertura: 🟢 ya lo tenemos · 🟡 parcial · 🔴 falta.

## 🔥 ALTO IMPACTO (suben la exactitud)

| Dato | Para qué | Dónde buscarlo | Gratis/Pago | Cobertura |
|---|---|---|---|---|
| **xG por partido (TODOS)** | Mejor medida de quién mereció ganar | FBref, Understat, Opta/StatsPerform | FBref scrape / Opta pago | 🟡 solo WC2018/22 (StatsBomb) + equipo actual |
| **Cuotas de cierre históricas** | El mejor predictor (mercado) | OddsPortal, Pinnacle, football-data.co.uk | scrape / pago | 🟡 solo snapshot 2026 |
| **Alineaciones / quién jugó (apariciones)** | Saber si el crack jugó; trayectoria real por partido | Transfermarkt, API-Football, StatsBomb | pago (2026) / free 2018-22 | 🔴 |
| **Lesiones y suspensiones** | Bajar fuerza si falta titular | Transfermarkt, API-Football, Sofascore | pago / scrape | 🔴 |

## 🟡 IMPACTO MEDIO (refinan / dan contexto)

| Dato | Para qué | Dónde | Gratis/Pago | Cobertura |
|---|---|---|---|---|
| **Stats por jugador** (asistencias, pases, regates, xA, minutos) | Rendimiento real del jugador | FBref, StatsBomb, Sofascore | scrape / pago | 🟡 2018/22 |
| **Tiros y tiros a puerta** por partido | Volumen ofensivo | FBref, StatsBomb | scrape | 🟡 2018/22 |
| **Formaciones / táctica** (4-3-3…) | Matchup táctico | StatsBomb, Opta, Sofascore | free 2018/22 / pago | 🟡 |
| **Rating de jugadores** (Sofascore por partido / FIFA-EA) | Calidad individual | Sofascore, SoFIFA, Kaggle | scrape / CSV | 🔴 |
| **Valor de mercado del plantel** | Proxy de calidad | Transfermarkt | scrape | 🔴 |
| **Árbitro: historial de tarjetas/penales** | Sesgo disciplinario | Transfermarkt, worldfootball | scrape | 🟡 (solo nombre 2026) |
| **Stats de portero** (paradas, % parada, goles evitados) | Defensa real | FBref, StatsBomb | scrape | 🟡 2018/22 |

## 🟢 BAJO IMPACTO / informativo

| Dato | Para qué | Dónde | Gratis/Pago | Cobertura |
|---|---|---|---|---|
| **Córners / faltas / saques** por partido | Estilo de juego | StatsBomb, FBref | free 2018/22 | 🟡 |
| **Posesión / PPDA / presión** | Estilo | FBref, StatsBomb | scrape | 🟡 |
| **Clima histórico** (para entrenar efecto clima) | Efecto lluvia/calor | Open-Meteo (historical, gratis) | **gratis** | 🔴 (fácil de bajar) |
| **Asistencia / aforo** | Empuje de público | Wikipedia, RSSSF | scrape | 🔴 |
| **Entrenador** (antigüedad, % victorias) | Efecto DT | Transfermarkt | scrape | 🔴 |
| **Edad/físico del jugador** | Fatiga por edad | ya en squads (DOB) | **gratis** | 🟢 (en squads_2026) |

## ✅ Lo que YA tenemos (no buscar)
Resultados de todos los internacionales (1872+), goleadores con minuto, penales,
tandas de penales, Elo, xG por equipo (snapshot), planteles 2026, cuotas 2026,
clima por sede, xG/tarjetas/faltas de WC2018-2022 (StatsBomb).

## 🎯 Si solo pudieras conseguir 2 cosas
1. **xG por partido de todos los torneos** (FBref/Opta) → el mayor salto de exactitud.
2. **Cuotas de cierre históricas** (OddsPortal/Pinnacle) → el mejor predictor para validar y mejorar.

## ⚠️ Nota
La mayoría de lo 🔴/🟡 está en sitios que **bloquean bots** (FBref, Sofascore,
Transfermarkt) o requieren **API de pago** (Opta/SportMonks/Sofascore API).
Lo que es **abierto** (StatsBomb GitHub, Open-Meteo, APIs free con key) ya está
en el toolkit (`HERRAMIENTAS.md`).
