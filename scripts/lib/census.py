"""Census API helpers (adapted from foreign-born-map/bake_county_data.py).

The API key is used only at fetch time and is never written into any output.
"""
import json
import time
import urllib.parse
import urllib.request


def chunk(arr, size):
    return [arr[i:i + size] for i in range(0, len(arr), size)]


def fetch_batch(year, vars_, geo_for, geo_in=None, key="", timeout=120, retries=3):
    """Fetch one batch of variables for a geography. Returns the raw rows
    (list of lists, first row is the header)."""
    params = {"get": ",".join(["NAME"] + vars_), "for": geo_for}
    if geo_in:
        params["in"] = geo_in
    qs = urllib.parse.urlencode(params, safe=":*")
    url = f"https://api.census.gov/data/{year}/acs/acs5?{qs}"
    if key:
        url += f"&key={key}"
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Census fetch failed after {retries} tries: {last_err}")
