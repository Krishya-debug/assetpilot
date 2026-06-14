"""Deterministic risk analysis. No LLM anywhere in this file on purpose.

The agent cites these numbers. Risk scoring is
plain, testable pandas:

    risk = (w_age * age_norm
            + w_total * total_breaks_norm
            + w_recent * recent_breaks_norm) * material_factor * 100

normalized within the dataset, clipped to 0–100, then bucketed into
High / Medium / Low priority tiers.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import config


def _norm(series: pd.Series) -> pd.Series:
    """Min-max normalize to 0..1; constant series normalize to 0."""
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or hi == lo:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)


def material_factor(material: object) -> float:
    key = str(material).strip().lower()
    return config.MATERIAL_FACTORS.get(key, config.MATERIAL_FACTORS["unknown"])


def assign_tier(score: float) -> str:
    if score >= config.TIER_THRESHOLDS["High"]:
        return "High"
    if score >= config.TIER_THRESHOLDS["Medium"]:
        return "Medium"
    return "Low"


def score_assets(breaks: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Aggregate break events per asset and compute a 0–100 risk score.

    Parameters
    ----------
    breaks : one row per break event (canonical schema from fetcher).
    now    : injectable clock for reproducible tests.
    """
    now = now or datetime.now()
    df = breaks.copy()
    df["break_date"] = pd.to_datetime(df["break_date"])
    recent_cutoff = now - pd.DateOffset(years=config.RECENT_YEARS)

    grouped = df.groupby("asset_id")
    assets = grouped.agg(
        district=("district", "first"),
        material=("material", "first"),
        diameter_mm=("diameter_mm", "first"),
        install_year=("install_year", "first"),
        total_breaks=("break_date", "count"),
        last_break=("break_date", "max"),
    )
    assets["recent_breaks"] = grouped["break_date"].apply(
        lambda s: int((s >= recent_cutoff).sum())
    )
    assets["age_years"] = (
        now.year - pd.to_numeric(assets["install_year"], errors="coerce")
    ).clip(lower=0)
    # Assets with unknown install year get the dataset's median age.
    assets["age_years"] = assets["age_years"].fillna(assets["age_years"].median())

    w = config.RISK_WEIGHTS
    base = (
        w["age"] * _norm(assets["age_years"])
        + w["total_breaks"] * _norm(assets["total_breaks"])
        + w["recent_breaks"] * _norm(assets["recent_breaks"])
    )
    factors = assets["material"].map(material_factor)
    assets["risk_score"] = (base * factors * 100).clip(0, 100).round(1)
    assets["tier"] = assets["risk_score"].map(assign_tier)

    return assets.sort_values("risk_score", ascending=False).reset_index()


def district_summary(assets: pd.DataFrame) -> pd.DataFrame:
    """Per-district rollup the agent uses for the regional view."""
    return (
        assets.groupby("district")
        .agg(
            assets=("asset_id", "count"),
            high_tier=("tier", lambda s: int((s == "High").sum())),
            mean_risk=("risk_score", "mean"),
            total_breaks=("total_breaks", "sum"),
        )
        .round({"mean_risk": 1})
        .sort_values("mean_risk", ascending=False)
        .reset_index()
    )


def dataset_summary(breaks: pd.DataFrame) -> dict:
    """Lightweight description of the loaded dataset (for the agent)."""
    return {
        "break_events": int(len(breaks)),
        "unique_assets": int(breaks["asset_id"].nunique()),
        "districts": sorted(breaks["district"].astype(str).unique().tolist()),
        "date_range": [
            str(breaks["break_date"].min().date()),
            str(breaks["break_date"].max().date()),
        ],
        "columns": list(breaks.columns),
    }
