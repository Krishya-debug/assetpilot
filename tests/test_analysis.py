"""Tests for the deterministic risk model.

Run: pytest
"""
from datetime import datetime

import pandas as pd
import pytest

from assetpilot import analysis


NOW = datetime(2026, 6, 1)


def make_breaks(rows):
    df = pd.DataFrame(
        rows,
        columns=[
            "asset_id", "district", "material",
            "diameter_mm", "install_year", "break_date",
        ],
    )
    df["break_date"] = pd.to_datetime(df["break_date"])
    return df


@pytest.fixture
def breaks():
    return make_breaks(
        [
            # Old cast iron, many recent breaks -> should rank highest
            ["WM-A", "North York", "Cast Iron", 150, 1940, "2024-01-10"],
            ["WM-A", "North York", "Cast Iron", 150, 1940, "2025-02-11"],
            ["WM-A", "North York", "Cast Iron", 150, 1940, "2025-11-03"],
            ["WM-A", "North York", "Cast Iron", 150, 1940, "2026-01-20"],
            # Mid-age ductile iron, one old break
            ["WM-B", "Scarborough", "Ductile Iron", 300, 1985, "2010-06-15"],
            # New PVC, one old break -> should rank lowest
            ["WM-C", "Scarborough", "PVC", 200, 2015, "2018-03-02"],
        ]
    )


def test_scores_are_bounded(breaks):
    assets = analysis.score_assets(breaks, now=NOW)
    assert assets["risk_score"].between(0, 100).all()


def test_old_breaky_pipe_ranks_highest(breaks):
    assets = analysis.score_assets(breaks, now=NOW)
    assert assets.iloc[0]["asset_id"] == "WM-A"
    assert assets.iloc[-1]["asset_id"] == "WM-C"


def test_recent_break_window(breaks):
    assets = analysis.score_assets(breaks, now=NOW).set_index("asset_id")
    assert assets.loc["WM-A", "recent_breaks"] == 4
    assert assets.loc["WM-B", "recent_breaks"] == 0


def test_deterministic(breaks):
    a = analysis.score_assets(breaks, now=NOW)
    b = analysis.score_assets(breaks, now=NOW)
    pd.testing.assert_frame_equal(a, b)


def test_tier_assignment():
    assert analysis.assign_tier(85.0) == "High"
    assert analysis.assign_tier(55.0) == "Medium"
    assert analysis.assign_tier(10.0) == "Low"


def test_material_factor_unknown_default():
    assert analysis.material_factor("vibranium") == 1.0


def test_district_summary_shape(breaks):
    assets = analysis.score_assets(breaks, now=NOW)
    summary = analysis.district_summary(assets)
    assert set(summary.columns) == {
        "district", "assets", "high_tier", "mean_risk", "total_breaks",
    }
    assert summary["assets"].sum() == 3
