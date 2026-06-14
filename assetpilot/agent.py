"""The agent loop: Claude plans its own steps via tool use.

Flow: system prompt sets the rules -> model calls tools -> we execute and
return results -> repeat until the model saves the briefing and stops.
Every step lands in a run log for transparency and debugging.
"""
from __future__ import annotations

from . import config
from .tools import TOOL_DEFINITIONS, ToolContext

SYSTEM_PROMPT = """\
You are AssetPilot, an infrastructure asset triage analyst for Ontario
municipal data. You produce a condition briefing a project manager can
forward without edits.

Hard rules:
1. Every number you write MUST come from a tool result in this conversation.
   Never estimate, extrapolate, or invent figures.
2. Workflow: fetch_asset_data -> compute_risk_scores -> get_district_summary
   -> save_briefing (exactly once) -> stop.
3. Briefing format (markdown):
   - Title with the date and data source
   - "Bottom line" — 3 sentences max, lead with the single most urgent finding
   - "Top priority assets" — table of the highest-risk assets and a short
     'why' note for the top 3, citing their actual age/breaks/material
   - "District view" — 2–4 sentences comparing districts
   - "Method note" — 2 sentences: the risk score formula inputs and weights,
     and the recent-breaks window, so readers know where numbers come from
4. Plain language. No hype. A reader with zero data background should
   understand every sentence.
"""


def run_agent(source: str = "sample") -> ToolContext:
    import anthropic  # lazy import so --no-llm mode needs no API package

    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key, or run with --no-llm for the deterministic briefing."
        )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    ctx = ToolContext()
    messages = [
        {
            "role": "user",
            "content": (
                f"Generate today's asset condition briefing using the "
                f"'{source}' data source."
            ),
        }
    ]

    for turn in range(config.MAX_AGENT_TURNS):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break  # the model is done

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [agent] turn {turn + 1}: {block.name}({block.input})")
                result = ctx.dispatch(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    log_path = ctx.save_run_log()
    print(f"  [agent] run log saved to {log_path}")
    return ctx
