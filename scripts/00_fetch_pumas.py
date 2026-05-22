#!/usr/bin/env python3
"""Fetch the 55 NYC 2020 PUMA boundaries, CLIPPED TO THE SHORELINE, with
neighborhood names.

Geometry: NYC Dept. of City Planning "2020 Public Use Microdata Areas" (NYC Open
Data pikk-p9nv) — clipped to the shoreline so the choropleth does not bleed into
rivers and the harbor. (The Census TIGER PUMA polygons include water.)

Names: Census TIGERweb 2020 PUMA layer, where the official NAME begins with
"NYC-" (e.g. "NYC-Queens Community District 3--Jackson Heights & North Corona
PUMA"), joined to the DCP geometry by PUMA code.

Output: docs/data/pumas.geojson  (EPSG:4326, coords rounded to ~1m)
No API key required.
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "pumas.geojson"

DCP = "https://data.cityofnewyork.us/resource/pikk-p9nv.geojson?$limit=1000"
TIGER = ("https://tigerweb.geo.census.gov/arcgis/rest/services/"
         "TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/0/query")


def clean_name(raw):
    name = re.sub(r"\s*PUMA$", "", (raw or "").strip())
    boro = ""
    m = re.match(r"NYC-([A-Za-z ]+?) Community District", name)
    if m:
        boro = m.group(1).strip()
    else:
        m2 = re.match(r"NYC-([A-Za-z ]+?)[ \-]", name)
        if m2:
            boro = m2.group(1).strip()
    label = name.split("--")[-1].strip() if "--" in name else name.replace("NYC-", "")
    return boro, label


def fetch_names():
    """geoid -> (boro, label) from TIGERweb."""
    params = {"where": "STATE='36' AND NAME LIKE 'NYC%'",
              "outFields": "GEOID,NAME", "returnGeometry": "false", "f": "json"}
    url = TIGER + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        data = json.loads(r.read())
    out = {}
    for f in data.get("features", []):
        a = f["attributes"]
        out[a["GEOID"]] = clean_name(a.get("NAME", ""))
    return out


def round_geom(geom, nd=5):
    def rc(coords):
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], nd), round(coords[1], nd)]
        out = [rc(c) for c in coords]
        # drop consecutive duplicate points in rings
        if out and isinstance(out[0][0], (int, float)):
            ded = [out[0]]
            for p in out[1:]:
                if p != ded[-1]:
                    ded.append(p)
            return ded
        return out
    return {"type": geom["type"], "coordinates": rc(geom["coordinates"])}


def main():
    names = fetch_names()
    with urllib.request.urlopen(DCP, timeout=120) as r:
        dcp = json.loads(r.read())

    feats = []
    for f in dcp.get("features", []):
        puma = (f["properties"].get("puma") or "").strip()
        if not puma:
            continue
        geoid = "36" + puma.zfill(5)
        boro, label = names.get(geoid, ("", f"PUMA {puma}"))
        feats.append({
            "type": "Feature",
            "properties": {"geoid": geoid, "name": label, "boro": boro},
            "geometry": round_geom(f["geometry"]),
        })
    feats.sort(key=lambda x: x["properties"]["geoid"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              separators=(",", ":")))
    print(f"wrote {len(feats)} shoreline-clipped NYC PUMAs -> {OUT} "
          f"({OUT.stat().st_size/1024:.0f} KB)")
    unnamed = [f["properties"]["geoid"] for f in feats if f["properties"]["name"].startswith("PUMA ")]
    if unnamed:
        print(f"  WARNING: {len(unnamed)} PUMAs without a TIGER name: {unnamed}")
    for f in feats[:5]:
        p = f["properties"]
        print(f"  {p['geoid']}  {p['boro']:14s} {p['name']}")


if __name__ == "__main__":
    main()
