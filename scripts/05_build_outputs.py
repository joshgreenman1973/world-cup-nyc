#!/usr/bin/env python3
"""Assemble final frontend payloads from 03 (pre) + 04 (Foursquare cache).

Writes:
  docs/data/teams/<CODE>.json   per-team choropleth + venues + stats
  docs/data/manifest.json       team index for the selector + global caveats
  docs/data/nation_mapping.json copy of the mapping (for the methodology modal)

Venues are filtered to price tier < 4 (no $$$$), sorted well-rated-affordable
first, unrated last. No API key required.
"""
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "data" / "raw" / "teams_pre.json"
CACHE = ROOT / "data" / "raw" / "fsq_cache.json"
TEAMS = ROOT / "config" / "teams.json"
MAPPING = ROOT / "config" / "nation_mapping.json"
OUTDIR = ROOT / "docs" / "data"
TEAMDIR = OUTDIR / "teams"

ACS_RELEASE = "American Community Survey 2019-2023 5-year estimates"


def venue_sort_key(v):
    # No ratings source (no free, terms-compliant provider), so order by
    # rating when present, else alphabetically by name.
    rated = v.get("rating") is not None
    return (not rated, -(v.get("rating") or 0), v.get("name", ""))


def main():
    pre = json.loads(PRE.read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    teams_cfg = json.loads(TEAMS.read_text())
    mapping = json.loads(MAPPING.read_text())

    TEAMDIR.mkdir(parents=True, exist_ok=True)
    # clear stale per-team files
    for old in TEAMDIR.glob("*.json"):
        old.unlink()

    built = {}
    for code, d in pre.items():
        venues = []
        for c in d.get("candidates", []):
            enr = cache.get(c["camis"]) or {}
            price = enr.get("price")
            if price == 4:  # drop $$$$ — costly spots make poor game-watching
                continue
            venues.append({
                "name": c["dba"],
                "lat": c["lat"], "lon": c["lon"],
                "puma": c["puma"], "puma_name": c["puma_name"],
                "cuisine": c["cuisine"], "boro": c["boro"],
                "rating": enr.get("rating"),
                "price": price,
                "fsq_id": enr.get("fsq_id"),
            })
        venues.sort(key=venue_sort_key)

        rated = [v["rating"] for v in venues if v["rating"] is not None]
        median_rating = round(statistics.median(rated), 1) if rated else None
        n_aff_rated = sum(1 for v in venues
                          if v["rating"] is not None and v["rating"] >= 7.5
                          and v["price"] in (1, 2))

        payload = {
            "code": code,
            "nation": d["nation"],
            "flag": d["flag"],
            "confederation": d["confederation"],
            "host": d["host"],
            "b05006": d["b05006"],
            "cuisines": d["cuisines"],
            "notes": d["notes"],
            "nyc_total": d["nyc_total"],
            "choropleth": d["choropleth"],
            "top_pumas": d["top_pumas"],
            "top_puma_names": d["top_puma_names"],
            "venues": venues,
            "stats": {
                "nyc_total": d["nyc_total"],
                "top_neighborhood": d["top_puma_names"][0] if d["top_puma_names"] else None,
                "n_venues": len(venues),
                "n_affordable_rated": n_aff_rated,
                "median_rating": median_rating,
            },
            "data_quality": d["data_quality"],
        }
        (TEAMDIR / f"{code}.json").write_text(json.dumps(payload, separators=(",", ":")))
        built[code] = payload["data_quality"]

    # manifest: every team SLOT (including unresolved TBD), for the selector
    team_index = []
    for t in teams_cfg["teams"]:
        code = t["code"]
        if t.get("qualified") and t.get("nation") and code in built:
            team_index.append({
                "code": code, "nation": t["nation"], "flag": t.get("flag", ""),
                "confederation": t.get("confederation", ""),
                "data_quality": built[code], "qualified": True,
            })
        else:
            team_index.append({
                "code": code, "nation": t.get("nation"), "flag": t.get("flag", ""),
                "confederation": t.get("confederation", ""),
                "data_quality": "tbd", "qualified": False,
                "note": t.get("note", ""),
            })

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tournament": teams_cfg.get("tournament", ""),
        "acs_release": ACS_RELEASE,
        "geography": "Public Use Microdata Areas (PUMAs), the 55 NYC neighborhoods the Census tabulates country-of-birth for",
        "teams": team_index,
        "sources": [
            {"name": "ACS 5-year, table B05006 (place of birth for the foreign-born)",
             "agency": "U.S. Census Bureau", "endpoint": "https://api.census.gov/data/2023/acs/acs5"},
            {"name": "DOHMH Restaurant Inspection Results (cuisine + location)",
             "agency": "NYC Dept. of Health and Mental Hygiene",
             "endpoint": "https://data.cityofnewyork.us/resource/43nn-pn8j"},
            {"name": "2020 PUMA boundaries (shoreline-clipped)",
             "agency": "NYC Dept. of City Planning",
             "endpoint": "https://data.cityofnewyork.us/resource/pikk-p9nv"},
        ],
        "caveats": [
            "\"Best neighborhood to watch\" is a heuristic from where a nation's New Yorkers live plus where that cuisine clusters — not a guide to which bars actually screen matches.",
            "Place of birth is not ancestry: U.S.-born children of immigrants are not counted, and undocumented residents are undercounted.",
            "Cuisine is not nationality; DOHMH cuisine tags are broad (e.g. \"Latin American\", \"African\") and were curated to nations by hand.",
            "Spots are not quality-ranked: no free, terms-compliant source lets us re-host restaurant ratings, so venues are shown unranked rather than as a curated \"best\" list.",
        ],
    }
    (OUTDIR / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    (OUTDIR / "nation_mapping.json").write_text(json.dumps(mapping, indent=2))

    # summary
    from collections import Counter
    qc = Counter(built.values())
    print(f"built {len(built)} team files; quality {dict(qc)}")
    print(f"manifest: {len(team_index)} slots "
          f"({sum(1 for t in team_index if t['qualified'])} resolved)")


if __name__ == "__main__":
    main()
