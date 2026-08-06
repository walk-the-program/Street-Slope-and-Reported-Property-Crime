"""Block-group socioeconomic controls from the ACS table-based summary files.

Uses the public summary-file mirror rather than the Census API. The API began
requiring a key; these .dat files do not, and each one carries every block group
in the country in a single download, which is what the multi-city design needs.
"""
from __future__ import annotations

import os

import pandas as pd
import requests

BASE = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/{year}"
    "/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat"
)
CACHE = "data/raw/acs"

# table -> {source column: friendly name}
WANTED = {
    "b19013": {"B19013_E001": "median_hh_income"},
    "b25077": {"B25077_E001": "median_home_value"},
    "b01003": {"B01003_E001": "population"},
    "b25001": {"B25001_E001": "housing_units"},
    "b25003": {"B25003_E001": "occupied_units", "B25003_E002": "owner_occupied"},
    "b25002": {"B25002_E003": "vacant_units"},
}


def _load_table(table: str, year: int = 2023) -> pd.DataFrame:
    os.makedirs(CACHE, exist_ok=True)
    path = f"{CACHE}/{table}_{year}.parquet"
    if os.path.exists(path):
        return pd.read_parquet(path)

    url = BASE.format(year=year, table=table)
    print(f"  downloading {table} ...", flush=True)
    raw = requests.get(url, timeout=600)
    raw.raise_for_status()
    tmp = f"{CACHE}/{table}_{year}.dat"
    with open(tmp, "wb") as fh:
        fh.write(raw.content)

    df = pd.read_csv(tmp, sep="|", dtype=str)
    # 1500000US<11-digit GEOID> identifies a block group
    df = df[df["GEO_ID"].str.startswith("1500000US")].copy()
    df["GEOID"] = df["GEO_ID"].str.replace("1500000US", "", regex=False)
    keep = ["GEOID"] + list(WANTED[table])
    df = df[keep]
    for c in WANTED[table]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.rename(columns=WANTED[table])
    df.to_parquet(path, index=False)
    os.remove(tmp)
    return df


def block_groups(year: int = 2023) -> pd.DataFrame:
    """All US block groups with the SES controls, indexed by 12-digit GEOID."""
    out = None
    for table in WANTED:
        df = _load_table(table, year)
        out = df if out is None else out.merge(df, on="GEOID", how="outer")

    # ACS jams negative sentinels into medians for suppressed cells
    for c in ("median_hh_income", "median_home_value"):
        out.loc[out[c] < 0, c] = pd.NA

    out["owner_share"] = out["owner_occupied"] / out["occupied_units"].replace(0, pd.NA)
    out["vacancy_rate"] = out["vacant_units"] / out["housing_units"].replace(0, pd.NA)
    return out


if __name__ == "__main__":
    bg = block_groups()
    print(f"{len(bg):,} block groups")
    print(bg.head().to_string())
