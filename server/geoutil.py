"""Tiện ích hình học nhẹ (không phụ thuộc thư viện ngoài)."""
import math


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _rings(geom):
    if not geom:
        return []
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return geom["coordinates"]
    return []


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def point_in_geom(lng, lat, geom):
    for poly in _rings(geom):
        if poly and _in_ring(lng, lat, poly[0]):
            if not any(_in_ring(lng, lat, h) for h in poly[1:]):
                return True
    return False


def bbox(geom):
    xs, ys = [], []
    for poly in _rings(geom):
        for ring in poly:
            for p in ring:
                xs.append(p[0]); ys.append(p[1])
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def centroid(geom):
    b = bbox(geom)
    if not b:
        return None
    polys = _rings(geom)
    ring = max((p[0] for p in polys), key=len)
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        f = x0 * y1 - x1 * y0
        a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-15:
        return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]
    return [cx / (3 * a), cy / (3 * a)]


def area_km2(geom):
    total = 0.0
    for poly in _rings(geom):
        for k, ring in enumerate(poly):
            if len(ring) < 3:
                continue
            lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
            s = 0.0
            for i in range(len(ring) - 1):
                x0 = ring[i][0] * 111320 * math.cos(lat0); y0 = ring[i][1] * 110574
                x1 = ring[i + 1][0] * 111320 * math.cos(lat0); y1 = ring[i + 1][1] * 110574
                s += x0 * y1 - x1 * y0
            total += (abs(s) / 2) * (1 if k == 0 else -1)
    return total / 1e6


def validate_geometry(geom):
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        return "Geometry phải là Polygon hoặc MultiPolygon"
    for poly in _rings(geom):
        for ring in poly:
            if len(ring) < 4:
                return "Vòng polygon cần ít nhất 4 điểm"
            for p in ring:
                if not (100 <= p[0] <= 112 and 8 <= p[1] <= 24):
                    return "Toạ độ nằm ngoài phạm vi Việt Nam (kiểm tra thứ tự lng,lat)"
    return None
