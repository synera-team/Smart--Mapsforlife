"""Grid maths shared by the server and the offline builder (tools/m4l_grid/build.py).

Equal-angle cells anchored at (0, 0): for nominal size S metres and reference latitude
ref_lat, dlat = S/111320 and dlng = S/(111320·cos ref_lat); cell (gx, gy) =
(floor(lng/dlng), floor(lat/dlat)) and its id is "gx:gy". A polygon "contains" a cell
when the cell centre is inside it (even-odd rule over all rings, so holes work).
"""
import collections
import math

M_PER_DEG = 111320.0
STATUS_CODES = {"eligible": "e", "pending_review": "p", "excluded": "x", "restricted": "r"}
STATUS_FROM_CODE = {v: k for k, v in STATUS_CODES.items()}
UNLOCKABLE = ("eligible", "pending_review")


def grid_step(cell_size_m, ref_lat):
    return cell_size_m / M_PER_DEG, cell_size_m / (M_PER_DEG * math.cos(math.radians(ref_lat)))


def cell_xy(lat, lng, dlat, dlng):
    return math.floor(lng / dlng), math.floor(lat / dlat)


def spans(rings, dlat, dlng):
    """Yield (gy, gx_first, gx_last) runs of cells whose centre lies inside `rings` ([[lng, lat], ...])."""
    rows = collections.defaultdict(list)
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if y1 == y2:
                continue
            lo, hi = min(y1, y2), max(y1, y2)
            # rows whose centre latitude yc satisfies lo < yc <= hi, i.e. where (y1 > yc) != (y2 > yc)
            for gy in range(math.floor(lo / dlat - .5) + 1, math.floor(hi / dlat - .5) + 1):
                rows[gy].append((x1, y1, x2, y2))
    for gy, edges in rows.items():
        yc = (gy + .5) * dlat
        xs = sorted(x1 + (yc - y1) * (x2 - x1) / (y2 - y1) for x1, y1, x2, y2 in edges if (y1 > yc) != (y2 > yc))
        for a, b in zip(xs[0::2], xs[1::2]):
            first, last = math.floor(a / dlng - .5) + 1, math.ceil(b / dlng - .5) - 1
            if first <= last:
                yield gy, first, last


def cells_in(rings, dlat, dlng):
    out = set()
    for gy, a, b in spans(rings, dlat, dlng):
        out.update((gx, gy) for gx in range(a, b + 1))
    return out


def geometry_rings(geom):
    """Rings of a GeoJSON Polygon/MultiPolygon, closed."""
    polys = [geom["coordinates"]] if geom.get("type") == "Polygon" else geom.get("coordinates") or []
    rings = []
    for poly in polys:
        for ring in poly:
            ring = [tuple(p[:2]) for p in ring]
            if len(ring) >= 3:
                rings.append(ring if ring[0] == ring[-1] else ring + [ring[0]])
    return rings


def line_cells(points, dlat, dlng):
    """Cells touched by a polyline, sampled four times per cell length."""
    out = set()
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        steps = max(1, int(max(abs(x2 - x1) / dlng, abs(y2 - y1) / dlat) * 4))
        for k in range(steps + 1):
            t = k / steps
            out.add((math.floor((x1 + (x2 - x1) * t) / dlng), math.floor((y1 + (y2 - y1) * t) / dlat)))
    return out
