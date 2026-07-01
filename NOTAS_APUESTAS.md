# Notas del modelo de apuestas — calibración e inclinaciones

Bitácora de ajustes a los mercados usados en el apartado 🎲 Apuestas. Todo se valida
**walk-forward** (cada partido se predice solo con datos previos; sin ver el futuro ni
el marcador que se predice).

## Análisis de inclinaciones (sesgos detectados)

| Mercado | Inclinación / sesgo | Diagnóstico |
|---|---|---|
| ⚽ Goles (O/U 2.5) | Bien calibrado | El **ensemble** es el más fiable (promedia λ de XGBoost+Estadístico+2026) |
| 🟨 Tarjetas (O/U 3.5) | **Sobreestimaba +0.9/partido** | El prior venía de Mundiales 2018/22 (3.35 tarj/partido); 2026 va más limpio (2.46) |
| 🚩 Córners (O/U 9.5) | Sesgo casi nulo, pero **alta varianza** | Casi impredecible: ningún modelo supera ~56% |

## Ajustes realizados

### 1. Tarjetas → modelo calibrado a 2026 (`src/cards2026.py`)  ✅ GRAN MEJORA
- **Antes:** prior histórico 2018/22 → **67.3%** O/U, sesgo **+0.9**.
- **Ajuste:** tasa de amarillas por equipo de ESTE Mundial (ESPN), con encogimiento
  hacia la media 2026 (K≈8). Walk-forward para validar; tasas finales para partidos futuros.
- **Después:** **76.4%** O/U, sesgo **−0.22** (prácticamente cero). MAE 1.27.
- Integrado en el motor (`simulate.Engine.cards`) y en el backtest.

### 2. Córners → sin cambio (techo de predictibilidad)
Variantes probadas (walk-forward, línea 9.5): tasa a-favor **52.7%**, favor+contra **50.9%**,
por remates **54.5%**, heurística-λ actual **56.4%**. Ninguna supera a la actual.
**Conclusión:** los córners son casi aleatorios (~56% techo). Se mantiene la heurística y
se marca como **NO fiable** (excluido de las recomendaciones de apuestas).

### 3. Goles → sin cambio (ya óptimo)
El ensemble acierta **80%** en O/U 2.5 (el mejor mercado). No se toca para no sobreajustar
con muestra pequeña (n=55).

## Estado final de fiabilidad (backtest walk-forward, 2026)

| Mercado | Acierto O/U | Recomendación |
|---|---|---|
| ⚽ Goles (ensemble) | **80%** | Mercado principal para apostar |
| 🟨 Tarjetas (2026) | **76%** | Fiable tras calibrar; usar líneas ~3.5 |
| 🚩 Córners | 56% | Evitar (poco fiable) |
| 1X2 "cuando hay ganador claro" | ~85% | Favoritos fuertes |

## Reglas de apuesta derivadas
- Priorizar **goles** y **tarjetas** (ya calibradas); evitar **córners**.
- En 1X2, solo favoritos claros; el valor real es escaso (Bet365 va afilada).
- Combinaciones: subir el pago con 2 patas, idealmente incluyendo la única apuesta con
  valor positivo, y stakes pequeños (¼ Kelly, tope 2%/apuesta).
