#!/usr/bin/env python3
"""Enrich the unique candidate venues from 03 with Foursquare ratings + price.

One-time offline bake. Persistent cache keyed by CAMIS means re-runs cost zero
new calls. A MAX_CALLS cap and a pre-flight count keep cost visible and bounded.

Usage: python3 04_enrich_foursquare.py [FSQ_KEY]
       (or set FSQ_API_KEY in the environment)
Optional: MAX_CALLS env (default 6000).

Reads:  data/raw/teams_pre.json
Writes: data/raw/fsq_cache.json   { camis: {rating, price, fsq_id, matched_name} | null }
The key is used only here and is NOT written into the output.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import fsq  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "data" / "raw" / "teams_pre.json"
CACHE = ROOT / "data" / "raw" / "fsq_cache.json"

KEY = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FSQ_API_KEY", "")).strip()
MAX_CALLS = int(os.environ.get("MAX_CALLS", "6000"))


def main():
    if not KEY:
        sys.exit("ERROR: Foursquare API key required (argv[1] or FSQ_API_KEY). "
                 "Free key at https://foursquare.com/developers/")

    pre = json.loads(PRE.read_text())
    # unique candidates by camis
    cand = {}
    for d in pre.values():
        for c in d.get("candidates", []):
            cand.setdefault(c["camis"], c)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [c for cid, c in cand.items() if cid not in cache]
    print(f"{len(cand)} unique candidates; {len(cache)} cached; "
          f"{len(todo)} to fetch now (cap {MAX_CALLS})", flush=True)
    if len(todo) > MAX_CALLS:
        sys.exit(f"ABORT: {len(todo)} calls exceeds MAX_CALLS={MAX_CALLS}. "
                 "Raise MAX_CALLS if you intend to spend this many calls.")

    calls = hits = 0
    for i, c in enumerate(todo, 1):
        try:
            res = fsq.search(c["dba"], c["lat"], c["lon"], KEY)
        except Exception as e:  # noqa: BLE001
            print(f"  fsq error for {c['dba']!r}: {e}", file=sys.stderr)
            res = None
            if calls == 0:
                # fail fast on the very first call (likely auth/version problem)
                sys.exit("First Foursquare call failed — check key / FSQ_API_VERSION / FSQ_BASE.")
        cache[c["camis"]] = res
        calls += 1
        if res:
            hits += 1
        if i % 50 == 0:
            CACHE.write_text(json.dumps(cache, separators=(",", ":")))
            print(f"  {i}/{len(todo)} (matched {hits})", flush=True)
        time.sleep(0.06)  # be polite

    CACHE.write_text(json.dumps(cache, separators=(",", ":")))
    print(f"done: {calls} calls, {hits} matched, {len(cache)} total cached -> {CACHE}")


if __name__ == "__main__":
    main()
