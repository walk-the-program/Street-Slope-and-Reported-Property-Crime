"""Re-download the four headline cities keeping the date and the offense text.

The original harvest threw both away once the classifier had run, because the
grid panel only ever needed a class label and a coordinate. Three of the
reviewer's requests cannot be answered without them:

  * separating vandalism from arson inside the no-loot control, since arson
    involves preparation and acute escape risk that vandalism does not;
  * pre- and post-2020 models, because the incident windows straddle the
    pandemic and differ by city;
  * matching theft to no-loot incidents on hour and day of week, so the two
    offense groups are compared under similar conditions rather than pooled
    across whatever times each happens to occur.

Only the four cities above the gradient floor are re-fetched. They carry every
mechanism test in the paper, and the low-relief cities appear only in the
heterogeneity analysis, which needs no incident-level detail.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import harvest
import harvest_arcgis as ha

OUT = "data/raw/crime_dated"

SOCRATA = {           # slug -> registry domain
    "sfgov": "data.sfgov.org",
    "seattle": "cos-data.seattle.gov",
    "cincinnati": "data.cincinnati-oh.gov",
}
ARCGIS = {"pittsburgh": "Pittsburgh"}


def _text_of(df, cols):
    """Rebuild the concatenated description exactly as the classifier saw it."""
    present = [c for c in cols if c in df.columns]
    text = df[present[0]].fillna("").astype(str)
    for c in present[1:]:
        text = text + " " + df[c].fillna("").astype(str)
    return text


def run():
    os.makedirs(OUT, exist_ok=True)
    reg = pd.read_csv("data/interim/registry.csv")
    rega = pd.read_csv("data/interim/registry_arcgis.csv")

    for slug, domain in SOCRATA.items():
        path = f"{OUT}/{slug}.parquet"
        if os.path.exists(path):
            print(f"{slug}: cached")
            continue
        row = reg[reg.domain == domain].iloc[0]
        # property_only=False: the no-loot split needs arson and vandalism rows
        # that the property filter would keep, but keeping everything also lets
        # the class shares be read against all reported crime.
        df = harvest.fetch_crime(row, property_only=False)
        descs = [c for c in str(row.all_desc).split(";") if c][:3]
        out = pd.DataFrame({
            "lat": df.lat, "lon": df.lon,
            "date": pd.to_datetime(df[row.date_col], errors="coerce", utc=True),
            "klass": df.klass, "loot_mass": df.loot_mass,
            "text": _text_of(df, descs),
        })
        out = out[out.date.notna()]
        out.to_parquet(path, index=False)
        print(f"{slug}: {len(out):,} rows  {out.date.min().date()} .. "
              f"{out.date.max().date()}")

    for slug, city in ARCGIS.items():
        path = f"{OUT}/{slug}.parquet"
        if os.path.exists(path):
            print(f"{slug}: cached")
            continue
        row = rega[rega.city == city].iloc[0]
        df = ha.fetch_city_arcgis(row, property_only=False)
        descs = [c for c in str(row.desc_fields).split(";") if c]
        out = pd.DataFrame({
            "lat": df.lat, "lon": df.lon,
            "date": pd.to_datetime(df.date, errors="coerce", utc=True),
            "klass": df.klass, "loot_mass": df.loot_mass,
            "text": _text_of(df, descs),
        })
        out = out[out.date.notna()]
        out.to_parquet(path, index=False)
        print(f"{slug}: {len(out):,} rows  {out.date.min().date()} .. "
              f"{out.date.max().date()}")

    print("done")


if __name__ == "__main__":
    run()
