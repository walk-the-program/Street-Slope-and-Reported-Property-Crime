"""Re-harvest and re-analyse after a change to the offense classifier.

Classification happens at download time in `harvest.fetch_crime`, so the cached
city tables carry whatever `crime_classes.classify_text` said when they were
built. A fix to the classifier therefore invalidates them and they must be
rebuilt rather than patched.

Two bugs motivated this rebuild, both of which silently corrupted the classes the
study's central tests depend on:

  * NIBRS 23G "Theft of Motor Vehicle Parts or Accessories" and 24I "Theft of
    Motor Vehicle License Plate" begin with the same words as 24O "Motor Vehicle
    Theft" and were landing in MVT. In Seattle that put 32,501 parts thefts into
    the one class where the candidate mechanisms make opposite predictions, and
    left MASS_5 empty.

  * Ohio charges vandalism as "CRIMINAL DAMAGING/ENDANGERING", which the pattern
    "criminal damage" did not match. Cincinnati's 33,149 no-loot records fell to
    OTHER, which is why Cincinnati was excluded from the no-loot control for
    lack of data -- a bug, not a data limitation.
"""
from __future__ import annotations

import os
import shutil
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

PANEL = ["data.sfgov.org", "cos-data.seattle.gov", "data.cincinnati-oh.gov",
         "data.kcmo.org", "data.montgomerycountymd.gov", "data.cityofchicago.org"]
BACKUP = "data/interim/cells_preclassifierfix"


def main():
    from harvest import run_one

    os.makedirs(BACKUP, exist_ok=True)
    reg = pd.read_csv("data/interim/registry.csv")

    for domain in PANEL:
        row = reg[reg.domain == domain]
        if row.empty:
            print(f"  [skip] {domain} not in registry")
            continue
        row = row.iloc[0]
        slug = domain.replace(".", "_")
        path = f"data/interim/cells/{slug}.parquet"

        # keep the old table so the effect of the fix can be quantified
        if os.path.exists(path):
            shutil.copy2(path, f"{BACKUP}/{slug}.parquet")
            os.remove(path)

        t0 = time.time()
        try:
            city, status, n = run_one(row)
            new = pd.read_parquet(path)
            cls = {c[2:]: int(new[c].sum()) for c in new.columns
                   if c.startswith("n_") and c != "n_total"}
            print(f"  [{status}] {city:22s} {n:7,} cells  ({time.time()-t0:.0f}s)")
            print(f"      {cls}", flush=True)
        except Exception as e:
            print(f"  [FAIL] {domain}: {type(e).__name__}: {str(e)[:100]}", flush=True)


def compare():
    """How much did the classifier fix actually move each class?"""
    rows = []
    for f in sorted(os.listdir(BACKUP)):
        old = pd.read_parquet(f"{BACKUP}/{f}")
        newp = f"data/interim/cells/{f}"
        if not os.path.exists(newp):
            continue
        new = pd.read_parquet(newp)
        for c in sorted(set(old.columns) | set(new.columns)):
            if not c.startswith("n_") or c == "n_total":
                continue
            o = int(old[c].sum()) if c in old else 0
            n = int(new[c].sum()) if c in new else 0
            if o or n:
                rows.append({"city": f.replace(".parquet", ""), "klass": c[2:],
                             "before": o, "after": n, "delta": n - o})
    d = pd.DataFrame(rows)
    d.to_csv("outputs/classifier_fix_impact.csv", index=False)
    return d


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        print(compare().to_string(index=False))
    else:
        main()
