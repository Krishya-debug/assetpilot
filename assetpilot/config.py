"""Central configuration for AssetPilot. All knobs live here or in .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / ".cache"

SAMPLE_DATA_PATH = DATA_DIR / "sample_watermain_breaks.csv"

# --- Anthropic API ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ASSETPILOT_MODEL", "claude-sonnet-4-6")
MAX_AGENT_TURNS = int(os.getenv("ASSETPILOT_MAX_TURNS", "12"))

# --- Live data (CKAN open data portal) ---
# Default: City of Toronto Open Data portal. Any CKAN portal works.
CKAN_BASE_URL = os.getenv(
    "CKAN_BASE_URL", "https://ckan0.cf.opendata.inter.prod-toronto.ca"
)
CKAN_PACKAGE_ID = os.getenv("CKAN_PACKAGE_ID", "watermain-breaks")
CKAN_PAGE_SIZE = 1000
CKAN_MAX_RECORDS = int(os.getenv("CKAN_MAX_RECORDS", "20000"))
CACHE_TTL_HOURS = float(os.getenv("CACHE_TTL_HOURS", "24"))

# Map portal-specific column names -> AssetPilot's canonical schema.
# Every open data portal names things differently; adjust per dataset.
# Canonical columns: asset_id, district, material, diameter_mm,
#                    install_year, break_date
COLUMN_MAP = {
    "asset_id": ["asset_id", "ASSET_ID", "WATMAIN_ID", "_id"],
    "district": ["district", "DISTRICT", "WARD", "ward", "AREA"],
    "material": ["material", "MATERIAL", "PIPE_MATERIAL"],
    "diameter_mm": ["diameter_mm", "DIAMETER", "PIPE_SIZE"],
    "install_year": ["install_year", "INSTALL_YEAR", "YEAR_INSTALLED"],
    "break_date": ["break_date", "BREAK_DATE", "Break_Date", "DATE"],
}

REQUIRED_COLUMNS = ["asset_id", "break_date"]

# --- Risk model ---
RECENT_YEARS = 5  # window for "recent breaks"
RISK_WEIGHTS = {"age": 0.40, "total_breaks": 0.35, "recent_breaks": 0.25}
MATERIAL_FACTORS = {
    "cast iron": 1.30,
    "concrete": 1.10,
    "ductile iron": 1.00,
    "steel": 0.95,
    "pvc": 0.80,
    "unknown": 1.00,
}
TIER_THRESHOLDS = {"High": 70.0, "Medium": 40.0}  # else Low
TOP_N = 15

# --- Email digest (optional; leave unset to write digest to disk only) ---
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DIGEST_TO = os.getenv("DIGEST_TO", "")
DIGEST_FROM = os.getenv("DIGEST_FROM", SMTP_USER)
