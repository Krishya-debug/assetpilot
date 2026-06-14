#!/usr/bin/env python3
"""AssetPilot CLI.

Usage:
  python run.py briefing                 # agent-written briefing (needs API key)
  python run.py briefing --no-llm        # deterministic briefing, no key needed
  python run.py briefing --live          # use live CKAN open data
  python run.py digest [--no-llm|--live] # briefing + weekly digest (+email if configured)
"""
from __future__ import annotations

import argparse
import sys

from assetpilot import briefing as briefing_mod
from assetpilot import config, digest as digest_mod


def make_briefing(source: str, no_llm: bool) -> str:
    """Returns the path of the saved briefing."""
    if no_llm or not config.ANTHROPIC_API_KEY:
        if not no_llm:
            print("No ANTHROPIC_API_KEY found. Falling back to --no-llm mode.")
        path = briefing_mod.save_briefing(source)
        print(f"Deterministic briefing saved: {path}")
        return path

    from assetpilot.agent import run_agent  # imports anthropic lazily

    print(f"Running agent (model: {config.MODEL}, source: {source})...")
    ctx = run_agent(source)
    if not ctx.briefing_path:
        print("Agent finished without saving a briefing; writing fallback.")
        return briefing_mod.save_briefing(source)
    print(f"Agent briefing saved: {ctx.briefing_path}")
    return ctx.briefing_path


def main() -> int:
    parser = argparse.ArgumentParser(description="AssetPilot")
    parser.add_argument("command", choices=["briefing", "digest"])
    parser.add_argument("--live", action="store_true", help="use live CKAN data")
    parser.add_argument("--no-llm", action="store_true", help="skip the agent")
    args = parser.parse_args()

    source = "live" if args.live else "sample"
    briefing_path = make_briefing(source, args.no_llm)

    if args.command == "digest":
        from pathlib import Path

        text = Path(briefing_path).read_text(encoding="utf-8")
        digest = digest_mod.build_digest(text)
        digest_path = digest_mod.save_digest(digest)
        print(f"Digest saved: {digest_path}")
        if digest_mod.email_configured():
            digest_mod.send_email(digest)
            print(f"Digest emailed to {config.DIGEST_TO}")
        else:
            print("Email not configured (SMTP_* unset). Digest saved to disk only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
