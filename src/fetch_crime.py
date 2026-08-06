"""Pull SF property-crime incidents from DataSF (Socrata) into a local parquet.

Only the fields the analysis needs. Paginates; Socrata caps a single page well
below the full result set.
"""
import io
import sys
import time

import pandas as pd
import requests

ENDPOINT = "https://data.sfgov.org/resource/wg3w-h783.csv"
START = "2018-01-01T00:00:00"

# Property-crime families. "Recovered Vehicle" is excluded: it records where a
# stolen car was found, not where it was taken.
CATEGORIES = [
    "Larceny Theft",
    "Burglary",
    "Motor Vehicle Theft",
    "Robbery",
    "Arson",
    "Malicious Mischief",
    "Stolen Property",
]

FIELDS = [
    "incident_datetime",
    "incident_year",
    "incident_category",
    "incident_subcategory",
    "incident_description",
    "latitude",
    "longitude",
    "cnn",
    "analysis_neighborhood",
    "police_district",
]

PAGE = 50_000


def fetch() -> pd.DataFrame:
    cats = ",".join(f"'{c}'" for c in CATEGORIES)
    where = f"incident_datetime >= '{START}' AND incident_category IN ({cats})"
    frames, offset = [], 0
    while True:
        params = {
            "$select": ",".join(FIELDS),
            "$where": where,
            "$order": "incident_datetime",
            "$limit": PAGE,
            "$offset": offset,
        }
        r = requests.get(ENDPOINT, params=params, timeout=300)
        r.raise_for_status()
        chunk = pd.read_csv(io.StringIO(r.text))
        if chunk.empty:
            break
        frames.append(chunk)
        print(f"  +{len(chunk):>6,} (offset {offset:,})", flush=True)
        offset += PAGE
        if len(chunk) < PAGE:
            break
        time.sleep(0.5)
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = fetch()
    print(f"fetched {len(df):,} rows")
    df = df.dropna(subset=["latitude", "longitude"])
    print(f"{len(df):,} rows with coordinates")
    df.to_parquet("data/raw/sf_property_crime.parquet", index=False)
    print(df["incident_year"].value_counts().sort_index().to_string())
