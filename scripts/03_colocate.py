#!/usr/bin/env python3
"""Co-location: for each team, rank PUMAs by that nation's resident count, take
the densest set (top PUMAs covering ~60% of the diaspora, 1-8), and keep only
cuisine-matching restaurants physically inside that set.

Reads: config/teams.json, config/nation_mapping.json,
       docs/data/puma_origins.json, docs/data/pumas.geojson, data/raw/dohmh.csv
Writes: data/raw/teams_pre.json  (choropleth + top_pumas + candidate venues,
        everything except Foursquare ratings)

No API key required.
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.geo import PumaIndex  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEAMS = ROOT / "config" / "teams.json"
MAPPING = ROOT / "config" / "nation_mapping.json"
ORIGINS = ROOT / "docs" / "data" / "puma_origins.json"
PUMAS = ROOT / "docs" / "data" / "pumas.geojson"
DOHMH = ROOT / "data" / "raw" / "dohmh.csv"
OUT = ROOT / "data" / "raw" / "teams_pre.json"

COVERAGE_TARGET = 0.60   # densest set covers >= this share of the diaspora
MAX_PUMAS = 8
MIN_PUMAS = 1


def smart_title(s):
    """Title-case DOHMH names (usually ALL CAPS) without mangling apostrophes or
    name prefixes: 'BEKY'S' -> "Beky's", "O'BRIEN" -> "O'Brien", 'MCNALLY' ->
    'McNally', '55 DELI-COFFEE SHOP' -> '55 Deli-Coffee Shop'."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return s

    def cap(w):
        lw = w.lower()
        if not lw:
            return lw
        chars = list(lw[0].upper() + lw[1:])
        for i in range(2, len(chars)):
            # capitalize after an apostrophe only for 1-letter prefixes (O', D', L')
            if chars[i - 1] == "'" and chars[i - 2].isalpha() and (i - 2 == 0 or not chars[i - 3].isalpha()):
                chars[i] = chars[i].upper()
        r = "".join(chars)
        if r[:2].lower() == "mc" and len(r) > 2 and r[2].isalpha():
            r = r[:2] + r[2].upper() + r[3:]
        return r

    parts = re.split(r"([ \-/])", s)
    return "".join(cap(p) if p not in (" ", "-", "/") else p for p in parts)


def reliab_class(est, moe):
    """ACS MOE is at 90% confidence -> SE = moe/1.645. CV = SE/est."""
    if not est or est <= 0 or moe is None or moe < 0:
        return "low"
    cv = (moe / 1.645) / est
    if cv < 0.15:
        return "high"
    if cv < 0.30:
        return "moderate"
    return "low"


def moe_of_sum(moes):
    vals = [m for m in moes if m is not None and m >= 0]
    if not vals:
        return None
    return round(math.sqrt(sum(m * m for m in vals)))


def main():
    teams = json.loads(TEAMS.read_text())["teams"]
    mapping = json.loads(MAPPING.read_text())
    origins = json.loads(ORIGINS.read_text())
    puma_fc = json.loads(PUMAS.read_text())
    puma_name = {f["properties"]["geoid"]: f["properties"]["name"] for f in puma_fc["features"]}

    # assign every cuisine-matching venue to a PUMA
    idx = PumaIndex(puma_fc)
    venues = []  # {camis, dba, lat, lon, puma, cuisine}
    n_rows = n_located = 0
    with DOHMH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n_rows += 1
            try:
                lat = float(row["latitude"]); lon = float(row["longitude"])
            except (ValueError, KeyError):
                continue
            puma = idx.locate(lon, lat)
            if not puma:
                continue
            n_located += 1
            venues.append({
                "camis": row["camis"],
                "dba": smart_title(row.get("dba")),
                "lat": round(lat, 6), "lon": round(lon, 6),
                "puma": puma,
                "cuisine": row.get("cuisine_description", ""),
                "boro": row.get("boro", ""),
            })
    print(f"located {n_located}/{n_rows} venues in NYC PUMAs", file=sys.stderr)

    # index venues by (puma, cuisine) for fast lookup
    by_puma_cuisine = {}
    for v in venues:
        by_puma_cuisine.setdefault((v["puma"], v["cuisine"]), []).append(v)

    out = {}
    all_candidate_camis = set()
    for t in teams:
        if not t.get("qualified") or not t.get("nation"):
            continue
        code = t["code"]
        nm = mapping.get(code)
        if not nm:
            print(f"  WARNING: no nation_mapping for {code}", file=sys.stderr)
            continue
        b_codes = nm.get("b05006", [])
        cuisines = nm.get("cuisines", [])
        is_host = bool(nm.get("host"))

        # per-PUMA count + MOE for this nation (sum across codes)
        choropleth = {}
        nyc_total = 0
        for geoid, rec in origins.items():
            est = 0; moes = []
            for c in b_codes:
                cell = rec.get(c)
                if cell:
                    est += cell["e"]
                    moes.append(cell["m"])
            if est > 0:
                m = moe_of_sum(moes)
                fb = rec.get("fb", 0)
                choropleth[geoid] = {
                    "count": est,
                    "moe": m,
                    "reliab": reliab_class(est, m),
                    "share_fb": round(est / fb, 4) if fb and fb > 0 else None,
                }
                nyc_total += est

        # densest set: top PUMAs covering COVERAGE_TARGET of the diaspora
        ranked = sorted(choropleth.items(), key=lambda kv: kv[1]["count"], reverse=True)
        top_pumas = []
        cum = 0
        for geoid, cell in ranked:
            top_pumas.append(geoid)
            cum += cell["count"]
            if len(top_pumas) >= MIN_PUMAS and nyc_total and cum / nyc_total >= COVERAGE_TARGET:
                break
            if len(top_pumas) >= MAX_PUMAS:
                break

        # candidate venues: cuisine match AND inside the densest set
        # (hosts skip the venue layer — "American" is everywhere, not meaningful)
        candidates = []
        if not is_host:
            seen = set()
            for geoid in top_pumas:
                for cui in cuisines:
                    for v in by_puma_cuisine.get((geoid, cui), []):
                        if v["camis"] in seen:
                            continue
                        seen.add(v["camis"])
                        candidates.append({
                            "camis": v["camis"], "dba": v["dba"],
                            "lat": v["lat"], "lon": v["lon"],
                            "puma": geoid, "puma_name": puma_name.get(geoid, ""),
                            "cuisine": v["cuisine"], "boro": v["boro"],
                        })
                        all_candidate_camis.add(v["camis"])

        # data quality flag
        floor = nm.get("diaspora_floor", 0)
        if is_host:
            quality = "host"
        elif not b_codes or nyc_total == 0:
            quality = "limited"
        elif nyc_total < floor:
            quality = "limited"
        else:
            quality = "ok"

        out[code] = {
            "code": code,
            "nation": t["nation"],
            "flag": t.get("flag", ""),
            "confederation": t.get("confederation", ""),
            "host": is_host,
            "b05006": b_codes,
            "cuisines": cuisines,
            "notes": nm.get("notes", ""),
            "nyc_total": nyc_total,
            "choropleth": choropleth,
            "top_pumas": top_pumas,
            "top_puma_names": [puma_name.get(g, "") for g in top_pumas],
            "candidates": candidates,
            "data_quality": quality,
        }

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {len(out)} teams -> {OUT}", file=sys.stderr)
    print(f"UNIQUE CANDIDATE VENUES TO ENRICH (Foursquare budget): "
          f"{len(all_candidate_camis)}", file=sys.stderr)

    # invariant check + a few summaries
    bad = 0
    for code, d in out.items():
        tp = set(d["top_pumas"])
        for c in d["candidates"]:
            if c["puma"] not in tp:
                bad += 1
    print(f"co-location invariant violations: {bad} (must be 0)", file=sys.stderr)
    sample = ["ITA", "ECU", "SEN", "JPN", "PAR", "ENG"]
    for code in sample:
        if code in out:
            d = out[code]
            print(f"  {code} {d['nation']:14s} total={d['nyc_total']:>7,} "
                  f"top={d['top_puma_names'][:2]} venues={len(d['candidates'])} "
                  f"[{d['data_quality']}]", file=sys.stderr)


if __name__ == "__main__":
    main()
