# AssetPilot

A tool-calling AI agent that triages Ontario infrastructure asset data into
prioritized, conicse condition briefings.

The agent pulls watermain break records (Ontario municipal open data), runs a
**deterministic** pandas risk model, and writes a briefing a project manager
can forward, with every number traceable to the analysis layer never
invented by the LLM. A scheduled GitHub Actions run produces a weekly digest.

## How AssetPilot is built:

- *The LLM plans and writes while Python computes.* Risk scores come from a
  plain, unit-tested pandas model (`assetpilot/analysis.py`). The agent's
  system prompt forbids it from using any number that didn't come from a tool
  result, and every run produces a step-by-step `run_log_*.json` for
  transparency.
- *Runs instantly with or without API key.* Bundled sample data means zero
  setup. `--live` switches to the real CKAN open data API (cached, with
  retries); `--no-llm` produces a deterministic template briefing with no API
  key at all.
- *Portal schemas vary, so normalization is config.* Each open
  data portal names columns differently; `COLUMN_MAP` in `config.py` adapts
  any CKAN dataset to the canonical schema, and missing required fields fail
  with instructions instead of producing an incorrect analysis.

## Quickstart

```bash
git clone https://github.com/yourhandle/assetpilot.git
cd assetpilot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Works immediately with no API key, bundled sample data:
python run.py briefing --no-llm

# Agent-written briefing (set your key first):
cp .env.example .env     # then put your ANTHROPIC_API_KEY in .env
python run.py briefing

# Weekly digest (saved to output/, emailed if SMTP_* is configured in .env):
python run.py digest

# Live Ontario open data instead of sample data:
python run.py briefing --live
```

Output lands in `output/`: the markdown briefing, the digest, and the agent
run log.

## Architecture

```
run.py                      CLI: briefing | digest, --live, --no-llm
assetpilot/
  config.py                 all settings, weights, column maps (env-driven)
  fetcher.py                CKAN API client: pagination, retries, 24h cache;
                            sample-data fallback; schema normalization
  analysis.py               deterministic risk model (pandas, unit-tested)
  tools.py                  agent tool schemas + dispatcher + run logging
  agent.py                  Claude tool-use loop (fetch → score → summarize → save)
  briefing.py               no-LLM template briefing (baseline + fallback)
  digest.py                 weekly digest + optional SMTP delivery
data/sample_watermain_breaks.csv   seeded synthetic dataset (see scripts/)
tests/test_analysis.py      risk model tests: bounds, ranking, determinism
.github/workflows/weekly-digest.yml   scheduled Monday run + artifact upload
```

### Agent flow

1. `fetch_asset_data` — load dataset, return summary (rows, assets, date range)
2. `compute_risk_scores` — run the risk model, return tier counts + top assets
3. `get_district_summary` — per-district rollup for the regional view
4. `save_briefing` — write the final markdown, exactly once

### Risk model

```
risk = (0.40·age + 0.35·total_breaks + 0.25·recent_breaks)  [min-max normalized]
       × material_factor (cast iron 1.3 … PVC 0.8) × 100, clipped to 0–100
Tiers: High ≥ 70, Medium ≥ 40, else Low
```

Weights, windows, and material factors are config, and can be tuned
in `config.py` with the tests still pinning the model's behavior.

## Live data notes

Default portal is the City of Toronto Open Data CKAN instance
(`watermain-breaks` package). Any CKAN portal works: set `CKAN_BASE_URL` and
`CKAN_PACKAGE_ID` in `.env`, and extend `COLUMN_MAP` if the dataset's column
names differ. Responses are cached in `.cache/` for 24 hours to be polite to
the portal.

Note: public break datasets often lack per-pipe attributes (material, install
year). The normalizer fills those with defaults, and the model's
unknown-attribute handling (median age, neutral material factor) keeps the
scoring honest. The bundled sample data is synthetic (seeded, labeled, and
modeled) based on Ontario municipal records so the full schema can be demonstrated.

## Scheduled digest (GitHub Actions)

`.github/workflows/weekly-digest.yml` runs every Monday (and on demand from
the Actions tab): installs deps, generates the digest, and uploads `output/`
as a build artifact. Add `ANTHROPIC_API_KEY` under repo **Settings → Secrets
and variables → Actions** for agent-written digests; without it the run
falls back to the deterministic briefing automatically.

## Tests

```bash
pytest
```

Covers score bounds, ranking sanity (old breaky cast iron outranks new PVC),
the recent-break window, tier thresholds, and full determinism.
