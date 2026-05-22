"""Point-in-polygon (ray casting) for assigning venues to PUMAs.

Works on GeoJSON Polygon / MultiPolygon geometries (lon/lat rings). A small
bounding-box pre-check keeps it fast across 55 PUMAs x thousands of points.
"""


def _ring_contains(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _polygon_contains(lon, lat, polygon):
    # polygon = [outer_ring, hole1, hole2, ...]
    if not polygon or not _ring_contains(lon, lat, polygon[0]):
        return False
    for hole in polygon[1:]:
        if _ring_contains(lon, lat, hole):
            return False
    return True


def _bbox(geometry):
    xs, ys = [], []
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    polys = coords if gtype == "MultiPolygon" else [coords]
    for poly in polys:
        for x, y in poly[0]:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


class PumaIndex:
    """Holds PUMA geometries with bbox pre-filter; .locate(lon,lat) -> geoid|None."""

    def __init__(self, geojson):
        self.entries = []
        for f in geojson["features"]:
            geom = f["geometry"]
            self.entries.append((f["properties"]["geoid"], _bbox(geom), geom))

    def locate(self, lon, lat):
        for geoid, (minx, miny, maxx, maxy), geom in self.entries:
            if lon < minx or lon > maxx or lat < miny or lat > maxy:
                continue
            gtype = geom["type"]
            polys = geom["coordinates"] if gtype == "MultiPolygon" else [geom["coordinates"]]
            for poly in polys:
                if _polygon_contains(lon, lat, poly):
                    return geoid
        return None
