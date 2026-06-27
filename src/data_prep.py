"""Carga y limpieza de los datos de martj42/international_results.

Funciones para:
- leer results.csv / goalscorers.csv / shootouts.csv / former_names.csv
- normalizar nombres de selecciones (mapear nombres históricos al actual)
- entregar un DataFrame de partidos limpio y ordenado cronológicamente
"""
from __future__ import annotations

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_repo")


def _data_path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def load_former_names() -> dict:
    """Devuelve dict {nombre_antiguo: nombre_actual}."""
    fn = pd.read_csv(_data_path("former_names.csv"))
    return dict(zip(fn["former"], fn["current"]))


# Algunos nombres en el dataset difieren del uso común; unificamos a una forma.
MANUAL_ALIASES = {
    "Czechoslovakia": "Czech Republic",
    "Yugoslavia": "Serbia",
    "Serbia and Montenegro": "Serbia",
    "West Germany": "Germany",
    "East Germany": "Germany",
    "Soviet Union": "Russia",
    "CIS": "Russia",
}


def build_alias_map() -> dict:
    aliases = dict(MANUAL_ALIASES)
    # former_names tiene prioridad para mapeos con rango de fechas, pero como
    # simplificación aplicamos el mapeo al nombre actual de forma global.
    for former, current in load_former_names().items():
        aliases.setdefault(former, current)
    return aliases


def normalize_team(series: pd.Series, aliases: dict) -> pd.Series:
    return series.map(lambda t: aliases.get(t, t))


def load_results(normalize: bool = True) -> pd.DataFrame:
    """Resultados limpios ordenados por fecha."""
    df = pd.read_csv(_data_path("results.csv"), parse_dates=["date"])
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)

    if normalize:
        aliases = build_alias_map()
        df["home_team"] = normalize_team(df["home_team"], aliases)
        df["away_team"] = normalize_team(df["away_team"], aliases)

    # Resultado: H (local), D (empate), A (visitante)
    df["result"] = "D"
    df.loc[df["home_score"] > df["away_score"], "result"] = "H"
    df.loc[df["home_score"] < df["away_score"], "result"] = "A"

    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_goalscorers(normalize: bool = True) -> pd.DataFrame:
    df = pd.read_csv(_data_path("goalscorers.csv"), parse_dates=["date"])
    df = df[df["minute"].notna()].copy()
    df = df[df["minute"] != "NA"]
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce")
    df = df.dropna(subset=["minute"])
    df["minute"] = df["minute"].astype(int)
    df = df[(df["minute"] >= 1) & (df["minute"] <= 120)]
    if normalize:
        aliases = build_alias_map()
        df["team"] = normalize_team(df["team"], aliases)
        df["home_team"] = normalize_team(df["home_team"], aliases)
        df["away_team"] = normalize_team(df["away_team"], aliases)
    return df.reset_index(drop=True)


def load_shootouts(normalize: bool = True) -> pd.DataFrame:
    df = pd.read_csv(_data_path("shootouts.csv"), parse_dates=["date"])
    if normalize:
        aliases = build_alias_map()
        df["home_team"] = normalize_team(df["home_team"], aliases)
        df["away_team"] = normalize_team(df["away_team"], aliases)
        df["winner"] = normalize_team(df["winner"], aliases)
    return df


def get_wc2026_fixtures(normalize: bool = True) -> pd.DataFrame:
    """TODOS los partidos de grupos del Mundial 2026 (jugados y por jugar).

    Lee el CSV crudo (sin descartar NA) y marca cada partido con `played`.
    Columnas: date, home_team, away_team, neutral, played, home_score, away_score.
    """
    df = pd.read_csv(_data_path("results.csv"), parse_dates=["date"])
    mask = (df["tournament"] == "FIFA World Cup") & (df["date"] >= "2026-01-01")
    df = df[mask].copy()
    hs = pd.to_numeric(df["home_score"], errors="coerce")
    as_ = pd.to_numeric(df["away_score"], errors="coerce")
    df["played"] = hs.notna() & as_.notna()
    df["home_score"] = hs
    df["away_score"] = as_
    if normalize:
        aliases = build_alias_map()
        df["home_team"] = normalize_team(df["home_team"], aliases)
        df["away_team"] = normalize_team(df["away_team"], aliases)
    return df.sort_values("date").reset_index(drop=True)


def get_wc2026_groupstage(df_results: pd.DataFrame | None = None) -> pd.DataFrame:
    """Partidos de la fase de grupos del Mundial 2026 (FIFA World Cup, 2026)."""
    if df_results is None:
        df_results = load_results()
    mask = (
        (df_results["tournament"] == "FIFA World Cup")
        & (df_results["date"] >= "2026-01-01")
    )
    return df_results[mask].sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    r = load_results()
    print("Partidos totales:", len(r))
    print("Rango fechas:", r["date"].min().date(), "->", r["date"].max().date())
    wc = get_wc2026_groupstage(r)
    print("Partidos WC2026 en datos:", len(wc))
