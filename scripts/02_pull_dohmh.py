#!/usr/bin/env python3
"""Pull NYC DOHMH restaurant inspections (Socrata 43nn-pn8j), restricted to the
cuisine_description values referenced by config/nation_mapping.json, deduped to
one record per CAMIS (most recent inspection).

Output: data/raw/dohmh.csv  (gitignored intermediate)
No API key required.
"""
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "config" / "nation_mapping.json"
OUT = ROOT / "data" / "raw" / "dohmh.csv"

BASE = "https://data.cityofnewyork.us/resource/43nn-pn8j.json"
FIELDS = ("camis,dba,boro,building,street,zipcode,latitude,longitude,"
          "cuisine_description,inspection_date")


def cuisine_union():
    mapping = json.loads(MAPPING.read_text())
    cuisines = set()
    for k, v in mapping.items():
        if isinstance(v, dict):
            cuisines.update(v.get("cuisines", []))
    return sorted(cuisines)


def paginate(where):
    offset = 0
    page = 50000
    while True:
        params = {
            "$select": FIELDS,
            "$where": where,
            "$order": "inspection_date DESC",
            "$limit": page,
            "$offset": offset,
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=120) as r:
            batch = json.loads(r.read())
        if not batch:
            break
        for row in batch:
            yield row
        if len(batch) < page:
            break
        offset += page


def main():
    cuisines = cuisine_union()
    quoted = ",".join("'" + c.replace("'", "''") + "'" for c in cuisines)
    where = (f"cuisine_description in ({quoted}) "
             "AND latitude IS NOT NULL AND longitude IS NOT NULL")
    print(f"{len(cuisines)} cuisines: {', '.join(cuisines)}", file=sys.stderr)

    seen = {}
    for row in paginate(where):
        cid = row.get("camis")
        if cid and cid not in seen:
            seen[cid] = row
    rows = list(seen.values())

    # validate: which mapped cuisines actually returned rows
    got = {r.get("cuisine_description") for r in rows}
    missing = [c for c in cuisines if c not in got]
    if missing:
        print(f"WARNING: cuisines with zero rows: {missing}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["camis", "dba", "boro", "building", "street", "zipcode",
            "latitude", "longitude", "cuisine_description", "inspection_date"]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} unique restaurants -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
