"""Foursquare Places API client (free tier) for ratings + price tier.

Uses the current Foursquare Places API:
  GET https://places-api.foursquare.com/places/search
  headers: Authorization: Bearer <SERVICE_KEY>, X-Places-Api-Version: <date>
Returns rating (0-10) and price (1-4) for the best name+location match.

Env overrides (in case Foursquare revises the API surface):
  FSQ_BASE          default https://places-api.foursquare.com/places/search
  FSQ_API_VERSION   default 2025-06-17
"""
import json
import os
import re
import urllib.parse
import urllib.request

BASE = os.environ.get("FSQ_BASE", "https://places-api.foursquare.com/places/search")
API_VERSION = os.environ.get("FSQ_API_VERSION", "2025-06-17")
FIELDS = "fsq_place_id,name,rating,price,location,distance"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _name_match(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    return na in nb or nb in na or na[:6] == nb[:6]


def search(name, lat, lon, key, radius=90, timeout=30):
    """Return dict {rating, price, fsq_id, matched_name} or None.
    rating: float 0-10 or None; price: int 1-4 or None."""
    params = {
        "query": name,
        "ll": f"{lat},{lon}",
        "radius": radius,
        "limit": 5,
        "fields": FIELDS,
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        "X-Places-Api-Version": API_VERSION,
        "accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    results = data.get("results", data) if isinstance(data, dict) else data
    if not results:
        return None
    # prefer a name match; else the nearest result
    chosen = None
    for res in results:
        if _name_match(name, res.get("name", "")):
            chosen = res
            break
    if chosen is None:
        chosen = min(results, key=lambda r: r.get("distance", 1e9))
        # if even the nearest has no name overlap and is >150m away, treat as miss
        if chosen.get("distance", 1e9) > 150 and not _name_match(name, chosen.get("name", "")):
            return None
    rating = chosen.get("rating")
    price = chosen.get("price")
    return {
        "rating": float(rating) if rating is not None else None,
        "price": int(price) if price is not None else None,
        "fsq_id": chosen.get("fsq_place_id") or chosen.get("fsq_id"),
        "matched_name": chosen.get("name"),
    }
