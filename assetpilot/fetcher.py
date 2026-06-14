"""Data acquisition layer.

Two modes:
  - sample: bundled synthetic dataset modeled on Ontario watermain-break data.
            Runs instantly, no network needed. Great for demos and tests.
  - live:   pulls records from a CKAN open data portal (default: City of
            Toronto) with pagination, retries, and a local cache.

Live portal schemas vary; ``normalize_columns`` adapts them to AssetPilot's
canonical schema using ``config.COLUMN_MAP``. If a dataset is missing required
fields, you get a clear error telling you what to adjust.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from . import config

CANONICAL_COLUMNS = [
    "asset_id",
    "district",
    "material",
    "diameter_mm",
    "install_year",
    "break_date",
]


class DataFetchError(RuntimeError):
    """Raised when live data can't be fetched or normalized."""


# ---------------------------------------------------------------- sample mode
def load_sample() -> pd.DataFrame:
    df = pd.read_csv(config.SAMPLE_DATA_PATH, parse_dates=["break_date"])
    return df


# ------------------------------------------------------------------ live mode
def _cache_path() -> Path:
    config.CACHE_DIR.mkdir(exist_ok=True)
    return config.CACHE_DIR / f"{config.CKAN_PACKAGE_ID}.json"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=config.CACHE_TTL_HOURS)


def _get_json(url: str, params: dict | None = None, retries: int = 3) -> dict:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as err:
            last_err = err
            time.sleep(2**attempt)  # 1s, 2s, 4s backoff
    raise DataFetchError(f"GET {url} failed after {retries} attempts: {last_err}")


def fetch_live_records() -> list[dict]:
    """Fetch all records for the configured CKAN package (cached)."""
    cache = _cache_path()
    if _cache_fresh(cache):
        return json.loads(cache.read_text())

    base = config.CKAN_BASE_URL.rstrip("/")
    pkg = _get_json(
        f"{base}/api/3/action/package_show", {"id": config.CKAN_PACKAGE_ID}
    )
    resources = [
        r for r in pkg["result"]["resources"] if r.get("datastore_active")
    ]
    if not resources:
        raise DataFetchError(
            f"Package '{config.CKAN_PACKAGE_ID}' has no datastore-active "
            "resources. Check CKAN_PACKAGE_ID, or use sample mode."
        )

    resource_id = resources[0]["id"]
    records: list[dict] = []
    offset = 0
    while len(records) < config.CKAN_MAX_RECORDS:
        page = _get_json(
            f"{base}/api/3/action/datastore_search",
            {"id": resource_id, "limit": config.CKAN_PAGE_SIZE, "offset": offset},
        )
        batch = page["result"]["records"]
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)

    cache.write_text(json.dumps(records))
    return records


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Map portal-specific column names onto the canonical schema."""
    out = pd.DataFrame()
    for canonical, candidates in config.COLUMN_MAP.items():
        for candidate in candidates:
            if candidate in raw.columns:
                out[canonical] = raw[candidate]
                break

    missing = [c for c in config.REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        raise DataFetchError(
            f"Live dataset is missing required columns {missing}. "
            f"Available columns: {list(raw.columns)}. "
            "Update COLUMN_MAP in assetpilot/config.py to map them, "
            "or run in sample mode (drop the --live flag)."
        )

    # Fill optional canonical columns with sane defaults.
    if "district" not in out.columns:
        out["district"] = "Unspecified"
    if "material" not in out.columns:
        out["material"] = "unknown"
    if "diameter_mm" not in out.columns:
        out["diameter_mm"] = pd.NA
    if "install_year" not in out.columns:
        out["install_year"] = pd.NA

    out["break_date"] = pd.to_datetime(out["break_date"], errors="coerce")
    out = out.dropna(subset=["break_date"])
    return out[CANONICAL_COLUMNS]


def load_live() -> pd.DataFrame:
    records = fetch_live_records()
    if not records:
        raise DataFetchError("Live fetch returned zero records.")
    return normalize_columns(pd.DataFrame(records))


def load(source: str = "sample") -> pd.DataFrame:
    if source == "live":
        return load_live()
    return load_sample()
