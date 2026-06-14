"""Deterministic briefing writer. No API key required.

This is both the offline fallback and a baseline to compare the agent
against: same numbers, template prose.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import analysis, config, fetcher


def build_briefing(source: str = "sample") -> str:
    breaks = fetcher.load(source)
    assets = analysis.score_assets(breaks)
    districts = analysis.district_summary(assets)
    info = analysis.dataset_summary(breaks)

    tiers = assets["tier"].value_counts().to_dict()
    top = assets.head(config.TOP_N)
    worst = top.iloc[0]
    worst_district = districts.iloc[0]

    lines: list[str] = []
    lines.append(
        f"# Asset Condition Briefing: {datetime.now():%B %d, %Y} "
        f"({source} data)\n"
    )
    lines.append("## Bottom line\n")
    lines.append(
        f"{tiers.get('High', 0)} of {len(assets)} assets are in the High "
        f"priority tier. The highest-risk asset is **{worst['asset_id']}** in "
        f"{worst['district']} (risk {worst['risk_score']}/100: "
        f"{int(worst['age_years'])}-year-old {worst['material']} main with "
        f"{int(worst['total_breaks'])} recorded breaks, "
        f"{int(worst['recent_breaks'])} in the last {config.RECENT_YEARS} "
        f"years). {worst_district['district']} carries the highest mean risk "
        f"({worst_district['mean_risk']}/100) and should anchor the next "
        f"inspection cycle.\n"
    )

    lines.append("## Top priority assets\n")
    cols = [
        "asset_id", "district", "material", "age_years",
        "total_breaks", "recent_breaks", "risk_score", "tier",
    ]
    table = top[cols].copy()
    table["age_years"] = table["age_years"].astype(int)
    lines.append(table.to_markdown(index=False))
    lines.append("")

    lines.append("## District view\n")
    lines.append(districts.to_markdown(index=False))
    lines.append("")

    w = config.RISK_WEIGHTS
    lines.append("## Method note\n")
    lines.append(
        f"Risk scores (0–100) weight asset age ({w['age']:.0%}), total "
        f"recorded breaks ({w['total_breaks']:.0%}), and breaks in the last "
        f"{config.RECENT_YEARS} years ({w['recent_breaks']:.0%}), adjusted "
        f"by a pipe-material factor. Data: {info['break_events']} break "
        f"events across {info['unique_assets']} assets, "
        f"{info['date_range'][0]} to {info['date_range'][1]}.\n"
    )
    return "\n".join(lines)


def save_briefing(source: str = "sample") -> str:
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    path = config.OUTPUT_DIR / f"briefing_{datetime.now():%Y-%m-%d}.md"
    path.write_text(build_briefing(source), encoding="utf-8")
    return str(path)
