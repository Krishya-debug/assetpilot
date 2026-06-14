"""Tools the agent can call, plus a dispatcher that logs every step.

Design rule: tools return *computed* JSON. The LLM's job is planning and
writing. Every number in the briefing is traceable to a tool result here.
"""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from . import analysis, config, fetcher

TOOL_DEFINITIONS = [
    {
        "name": "fetch_asset_data",
        "description": (
            "Load the watermain break dataset. Returns a summary: number of "
            "break events, unique assets, districts, and date range. Must be "
            "called before any analysis tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["sample", "live"],
                    "description": "sample = bundled demo data; live = CKAN portal",
                }
            },
            "required": ["source"],
        },
    },
    {
        "name": "compute_risk_scores",
        "description": (
            "Run the deterministic risk model over the loaded data. Returns "
            "tier counts and the top-N highest-risk assets with their age, "
            "material, break history, and risk score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": f"How many top assets to return (default {config.TOP_N})",
                }
            },
        },
    },
    {
        "name": "get_district_summary",
        "description": (
            "Per-district rollup: asset count, high-tier count, mean risk "
            "score, and total breaks. Use for the regional comparison section."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_briefing",
        "description": (
            "Save the final markdown briefing to disk. Call exactly once, "
            "after all analysis tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "Full briefing text"}
            },
            "required": ["markdown"],
        },
    },
]


class ToolContext:
    """Holds state across tool calls within one agent run."""

    def __init__(self) -> None:
        self.breaks: pd.DataFrame | None = None
        self.assets: pd.DataFrame | None = None
        self.briefing_path: str | None = None
        self.run_log: list[dict] = []

    # ----------------------------------------------------------- dispatch
    def dispatch(self, name: str, tool_input: dict) -> str:
        started = datetime.now()
        try:
            result = getattr(self, f"_tool_{name}")(**tool_input)
            status = "ok"
        except Exception as err:  # surface errors to the model, don't crash
            result = {"error": f"{type(err).__name__}: {err}"}
            status = "error"
        self.run_log.append(
            {
                "tool": name,
                "input": tool_input,
                "status": status,
                "elapsed_ms": int((datetime.now() - started).total_seconds() * 1000),
            }
        )
        return json.dumps(result, default=str)

    # -------------------------------------------------------------- tools
    def _tool_fetch_asset_data(self, source: str = "sample") -> dict:
        self.breaks = fetcher.load(source)
        return {"source": source, **analysis.dataset_summary(self.breaks)}

    def _tool_compute_risk_scores(self, top_n: int = config.TOP_N) -> dict:
        if self.breaks is None:
            return {"error": "No data loaded. Call fetch_asset_data first."}
        self.assets = analysis.score_assets(self.breaks)
        tiers = self.assets["tier"].value_counts().to_dict()
        top = self.assets.head(top_n)[
            [
                "asset_id",
                "district",
                "material",
                "install_year",
                "age_years",
                "total_breaks",
                "recent_breaks",
                "risk_score",
                "tier",
            ]
        ]
        return {
            "tier_counts": tiers,
            "risk_weights": config.RISK_WEIGHTS,
            "recent_window_years": config.RECENT_YEARS,
            "top_assets": top.to_dict(orient="records"),
        }

    def _tool_get_district_summary(self) -> dict:
        if self.assets is None:
            return {"error": "Run compute_risk_scores first."}
        return {"districts": analysis.district_summary(self.assets).to_dict(orient="records")}

    def _tool_save_briefing(self, markdown: str) -> dict:
        config.OUTPUT_DIR.mkdir(exist_ok=True)
        path = config.OUTPUT_DIR / f"briefing_{datetime.now():%Y-%m-%d}.md"
        path.write_text(markdown, encoding="utf-8")
        self.briefing_path = str(path)
        return {"saved_to": str(path), "characters": len(markdown)}

    # ----------------------------------------------------------- run log
    def save_run_log(self) -> str:
        config.OUTPUT_DIR.mkdir(exist_ok=True)
        path = config.OUTPUT_DIR / f"run_log_{datetime.now():%Y-%m-%d_%H%M%S}.json"
        path.write_text(json.dumps(self.run_log, indent=2), encoding="utf-8")
        return str(path)
