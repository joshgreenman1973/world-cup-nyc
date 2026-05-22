#!/usr/bin/env python3
"""Fetch ACS B05006 (place of birth for the foreign-born) at PUMA geography for
the 55 NYC PUMAs, including margins of error, for every country code referenced
by config/nation_mapping.json.

Why PUMA: detailed country-of-birth estimates have very large margins of error
at tract/NTA level. PUMAs are the smallest geography the Census tabulates B05006
directly, and NYC PUMAs carry official neighborhood names.

Usage: python3 01_fetch_acs_b05006.py [CENSUS_KEY]
       (or set CENSUS_API_KEY in the environment)

Output: docs/data/puma_origins.json
  { "<geoid>": { "name", "boro", "total", "fb",
                 "B05006_165E": {"e": 1200, "m": 300}, ... } }
The API key is used only here and is NOT written into the output.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.census import chunk, fetch_batch  # noqa: E402

ACS_YEAR = "2023"
ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "config" / "nation_mapping.json"
PUMAS = ROOT / "docs" / "data" / "pumas.geojson"
OUT = ROOT / "docs" / "data" / "puma_origins.json"

KEY = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CENSUS_API_KEY", "")).strip()


def main():
    if not KEY:
        sys.exit("ERROR: Census API key required (argv[1] or CENSUS_API_KEY). "
                 "Keys are free at https://api.census.gov/data/key_signup.html")

    mapping = json.loads(MAPPING.read_text())
    # union of estimate codes referenced by any nation
    est_codes = sorted({c for k, v in mapping.items()
                        if isinstance(v, dict)
                        for c in v.get("b05006", [])})
    moe_codes = [c[:-1] + "M" for c in est_codes]
    base = ["B05002_001E", "B05006_001E"]
    all_vars = base + est_codes + moe_codes
    print(f"{len(est_codes)} country codes, {len(all_vars)} variables total", flush=True)

    # NYC PUMA geoids + names from the boundary file
    puma_fc = json.loads(PUMAS.read_text())
    names = {f["properties"]["geoid"]: f["properties"] for f in puma_fc["features"]}
    nyc_geoids = set(names)

    merged = {}
    for i, batch in enumerate(chunk(all_vars, 46), 1):
        print(f"  batch {i}: {len(batch)} vars ...", flush=True)
        rows = fetch_batch(ACS_YEAR, batch,
                           geo_for="public use microdata area:*",
                           geo_in="state:36", key=KEY)
        headers = rows[0]
        si = headers.index("state")
        pi = headers.index("public use microdata area")
        for r in rows[1:]:
            geoid = r[si] + r[pi]
            if geoid not in nyc_geoids:
                continue
            d = merged.setdefault(geoid, {})
            for j, h in enumerate(headers):
                if h in ("NAME", "state", "public use microdata area"):
                    continue
                try:
                    d[h] = int(r[j])
                except (ValueError, TypeError):
                    d[h] = -1

    # assemble output: pair each estimate with its MOE
    out = {}
    for geoid, vals in merged.items():
        props = names.get(geoid, {})
        rec = {
            "name": props.get("name", ""),
            "boro": props.get("boro", ""),
            "total": vals.get("B05002_001E", -1),
            "fb": vals.get("B05006_001E", -1),
        }
        for c in est_codes:
            e = vals.get(c, -1)
            m = vals.get(c[:-1] + "M", -1)
            if e and e > 0:
                rec[c] = {"e": e, "m": m if m >= 0 else None}
        out[geoid] = rec

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {len(out)} PUMAs -> {OUT}")
    # spot-check a couple of well-known enclaves (codes that are in the mapping)
    for label, code in [("Ecuador", "B05006_170E"),
                        ("Italy", "B05006_023E")]:
        top = sorted(((v.get(code, {}).get("e", 0) or 0, v["name"]) for v in out.values()),
                     reverse=True)[:3]
        print(f"  top {label}: " + "; ".join(f"{n} ({c:,})" for c, n in top))


if __name__ == "__main__":
    main()
