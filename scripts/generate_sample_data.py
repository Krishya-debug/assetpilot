"""Generate the bundled sample dataset (deterministic, seeded).

Synthetic data modeled on Ontario municipal watermain-break records:
one row per break event. Older cast-iron mains break more often —
the generator encodes that so the risk model has real signal to find.

Run once: python scripts/generate_sample_data.py
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

DISTRICTS = ["Etobicoke York", "North York", "Scarborough", "Toronto & East York"]
MATERIALS = [
    ("Cast Iron", 0.40, (1925, 1975)),
    ("Ductile Iron", 0.30, (1965, 2000)),
    ("PVC", 0.20, (1985, 2018)),
    ("Concrete", 0.10, (1950, 1990)),
]
DIAMETERS = [150, 200, 250, 300, 400, 600]

N_ASSETS = 140
TODAY = date(2026, 6, 1)


def pick_material() -> tuple[str, tuple[int, int]]:
    r = random.random()
    cumulative = 0.0
    for name, weight, years in MATERIALS:
        cumulative += weight
        if r <= cumulative:
            return name, years
    return MATERIALS[-1][0], MATERIALS[-1][2]


def expected_breaks(material: str, age: int) -> float:
    base = {"Cast Iron": 4.5, "Concrete": 3.0, "Ductile Iron": 2.0, "PVC": 0.9}
    return base[material] * (0.4 + age / 100)


rows = []
for i in range(1, N_ASSETS + 1):
    asset_id = f"WM-{i:04d}"
    district = random.choice(DISTRICTS)
    material, (y0, y1) = pick_material()
    install_year = random.randint(y0, y1)
    diameter = random.choice(DIAMETERS)
    age = TODAY.year - install_year

    n_breaks = max(1, round(random.gauss(expected_breaks(material, age), 1.2)))
    earliest = max(date(install_year + 5, 1, 1), date(1995, 1, 1))
    span_days = (TODAY - earliest).days
    for _ in range(n_breaks):
        # Recent-weighted: breaks cluster toward the present for aging pipes.
        frac = random.random() ** (0.7 if material in ("Cast Iron", "Concrete") else 1.3)
        break_date = earliest + timedelta(days=int(frac * span_days))
        rows.append(
            {
                "asset_id": asset_id,
                "district": district,
                "material": material,
                "diameter_mm": diameter,
                "install_year": install_year,
                "break_date": break_date.isoformat(),
            }
        )

df = pd.DataFrame(rows).sort_values(["asset_id", "break_date"])
out = Path(__file__).resolve().parent.parent / "data" / "sample_watermain_breaks.csv"
out.parent.mkdir(exist_ok=True)
df.to_csv(out, index=False)
print(f"Wrote {len(df)} break events for {df['asset_id'].nunique()} assets -> {out}")
