"""Build the Hanoi-wide Fog-of-War grid from cached OpenStreetMap data (run fetch.py first).

    python tools/m4l_grid/build.py

Writes:
  server/m4l_data/hanoi_grid_v1.json.gz   cells (run-length encoded), wards/communes, display boundary, provenance
  docs/m4l/HANOI_GRID_REPORT.md           counts per status and per ward/commune, coverage checks

Grid: same equal-angle grid as the Cầu Giấy pilot (100 m, reference latitude 21.0), so cell ids
"gx:gy" are identical and pilot unlocks carry over unchanged.

Cell status (first match wins):
  restricted     centre inside landuse=military
  excluded       centre inside water (natural=water, waterway=riverbank)
  eligible       at least one public road/path (OSM highway, not motorway, not access=private/no) crosses the cell
  pending_review everything else inside the city — reachability unknown, not counted as a required cell
"""
import collections
import datetime
import gzip
import json
import math
import os
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import fetch  # noqa: E402
import m4l_grid as grid  # noqa: E402

CELL_M = 100
REF_LAT = 21.0
DLAT, DLNG = grid.grid_step(CELL_M, REF_LAT)
STATUS_CODES = grid.STATUS_CODES
OUT_DATA = os.path.join(ROOT, "server", "m4l_data", "hanoi_grid_v1.json.gz")
OUT_REPORT = os.path.join(ROOT, "docs", "m4l", "HANOI_GRID_REPORT.md")


# ---------------------------------------------------------------- geometry helpers
def slugify(text):
    text = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "D")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower()
    out, dash = [], False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-")


def assemble_rings(segments):
    """Join open way geometries (lists of (lng, lat)) into closed rings by matching end points."""
    rings, pending = [], [list(s) for s in segments if len(s) >= 2]
    while pending:
        ring = pending.pop()
        while ring[0] != ring[-1]:
            for i, seg in enumerate(pending):
                if seg[0] == ring[-1]:
                    ring += seg[1:]
                elif seg[-1] == ring[-1]:
                    ring += seg[-2::-1]
                elif seg[-1] == ring[0]:
                    ring[:0] = seg[:-1]
                elif seg[0] == ring[0]:
                    ring[:0] = seg[:0:-1]
                else:
                    continue
                pending.pop(i)
                break
            else:
                ring.append(ring[0])  # unclosable fragment: close it rather than drop it
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def element_rings(el):
    if el["type"] == "way":
        geom = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
        return [geom] if len(geom) >= 4 and geom[0] == geom[-1] else []
    segs = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in el.get("members", [])
            if m["type"] == "way" and m.get("geometry") and m.get("role") in ("outer", "inner", "")]
    return assemble_rings(segs)


def cells_in(rings):
    return grid.cells_in(rings, DLAT, DLNG)


def line_cells(points):
    return grid.line_cells(points, DLAT, DLNG)


def ring_area_km2(ring):
    lat0 = math.radians(REF_LAT)
    pts = [(x * 111.32 * math.cos(lat0), y * 111.32) for x, y in ring]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:]))) / 2


def simplify(ring, tol):
    """Douglas–Peucker for display only. A closed ring is split at the vertex farthest from its start,
    otherwise the first/last chord has zero length and every vertex would be dropped."""
    if len(ring) < 5:
        return [[round(x, 5), round(y, 5)] for x, y in ring]
    if ring[0] == ring[-1]:
        x0, y0 = ring[0]
        far = max(range(len(ring)), key=lambda k: (ring[k][0] - x0) ** 2 + (ring[k][1] - y0) ** 2)
        return _dp(ring[:far + 1], tol) + _dp(ring[far:], tol)[1:]
    return _dp(ring, tol)


def _dp(ring, tol):
    if len(ring) < 3:
        return [[round(x, 5), round(y, 5)] for x, y in ring]
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = ring[i], ring[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = 0.0, None
        for k in range(i + 1, j):
            d = abs(dy * (ring[k][0] - x1) - dx * (ring[k][1] - y1)) / norm
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [[round(x, 5), round(y, 5)] for (x, y), k in zip(ring, keep) if k]


# ---------------------------------------------------------------- build
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    city_data = fetch.city()
    rel = city_data["elements"][0]
    city_rings = element_rings(rel)
    city = cells_in(city_rings)
    outer_km2 = max(ring_area_km2(r) for r in city_rings)
    print(f"  thành phố: {len(city_rings)} vòng, {len(city):,} ô (diện tích vòng lớn nhất {outer_km2:,.0f} km²)", flush=True)

    units, unit_of = [], {}
    for el in sorted(fetch.units()["elements"], key=lambda e: e["tags"].get("name", "")):
        name = el["tags"].get("name", "")
        kind = "phuong" if name.startswith("Phường") else "xa" if name.startswith("Xã") else "khac"
        base = name.split(" ", 1)[1] if " " in name else name
        slug = ("xa-" if kind == "xa" else "") + slugify(base)
        rings = element_rings(el)
        idx = len(units)
        units.append({"slug": slug, "name": name, "kind": kind, "osm_relation": el["id"],
                      "area_km2": round(max((ring_area_km2(r) for r in rings), default=0), 2)})
        for cell in cells_in(rings):
            if cell in city:
                unit_of.setdefault(cell, idx)
    print(f"  đơn vị cấp xã: {len(units)}, ô có đơn vị: {len(unit_of):,}", flush=True)

    water = set()
    for el in fetch.water()["elements"]:
        water |= cells_in(element_rings(el))
    restricted = set()
    for el in fetch.restricted()["elements"]:
        restricted |= cells_in(element_rings(el))
    roads, road_ways, osm_stamps, missing = set(), 0, {city_data["osm3s"]["timestamp_osm_base"]}, []
    cached_only = "--cached-only" in sys.argv
    for box, get in fetch.road_tiles():
        try:
            data = get(cache_only=cached_only)
        except LookupError:
            missing.append(box)  # roads not downloaded yet: cells there stay pending_review
            continue
        osm_stamps.add(data["osm3s"]["timestamp_osm_base"])
        for el in data["elements"]:
            pts = [(p["lon"], p["lat"]) for p in el.get("geometry", []) if p]
            if len(pts) >= 2:
                roads |= line_cells(pts)
                road_ways += 1
    print(f"  mặt nước: {len(water & city):,} ô · quân sự: {len(restricted & city):,} ô · đường: {road_ways:,} tuyến → {len(roads & city):,} ô", flush=True)

    status = {}
    for cell in city:
        status[cell] = ("restricted" if cell in restricted else "excluded" if cell in water
                        else "eligible" if cell in roads else "pending_review")

    rows = collections.defaultdict(list)
    for (gx, gy) in sorted(city, key=lambda c: (c[1], c[0])):
        code, unit = STATUS_CODES[status[(gx, gy)]], unit_of.get((gx, gy), -1)
        run = rows[gy][-1] if rows[gy] else None
        if run and run[0] + run[1] == gx and run[2] == code and run[3] == unit:
            run[1] += 1
        else:
            rows[gy].append([gx, 1, code, unit])

    totals = collections.Counter(status.values())
    per_unit = collections.defaultdict(collections.Counter)
    for cell, st in status.items():
        per_unit[unit_of.get(cell, -1)][st] += 1
    boundary = {"type": "MultiPolygon", "coordinates": [[simplify(r, 0.0004)] for r in city_rings]}
    shown = [ring_area_km2(poly[0]) for poly in boundary["coordinates"]]
    assert all(len(poly[0]) >= 50 for poly in boundary["coordinates"]) and abs(max(shown) - outer_km2) / outer_km2 < 0.01, \
        f"ranh giới hiển thị sai lệch: {max(shown):.0f} km² so với {outer_km2:.0f} km²"
    meta = {
        "name": "Thành phố Hà Nội", "slug": "ha-noi",
        "source": f"OpenStreetMap relation {fetch.CITY_RELATION} (admin_level=4) + 126 relations admin_level=6; highway, natural=water, waterway=riverbank, landuse=military",
        "license": "ODbL 1.0 — © OpenStreetMap contributors (https://www.openstreetmap.org/copyright)",
        "osm_timestamp": max(osm_stamps), "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "crs": "EPSG:4326 (WGS84)", "cell_size_m": CELL_M, "ref_lat": REF_LAT,
        "admin_note": "Ranh giới cấp xã theo sắp xếp có hiệu lực 01/07/2025 do cộng đồng OSM số hóa; chưa đối chiếu bản đồ chính thức",
        "counts": dict(totals), "cells": len(city),
        "road_tiles_missing": missing,
    }
    os.makedirs(os.path.dirname(OUT_DATA), exist_ok=True)
    with gzip.open(OUT_DATA, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "units": units, "boundary": boundary,
                   "rows": [[gy, runs] for gy, runs in sorted(rows.items())]}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ghi {OUT_DATA} ({os.path.getsize(OUT_DATA) / 1e6:.2f} MB)", flush=True)
    write_report(meta, units, per_unit, outer_km2)


def write_report(meta, units, per_unit, outer_km2):
    db_wards = set()
    db = os.path.join(ROOT, "data", "xanh24.db")
    if os.path.exists(db):
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        db_wards = {r[0] for r in conn.execute("SELECT slug FROM wards")}
        conn.close()
    osm_slugs = {u["slug"] for u in units}
    c = meta["counts"]
    total = meta["cells"]
    lines = [
        "# Lưới Fog of War toàn Hà Nội — báo cáo dữ liệu", "",
        f"Sinh bởi `tools/m4l_grid/build.py` lúc {meta['built_at']} · dữ liệu OSM tại {meta['osm_timestamp']}.", "",
        "## Nguồn và giấy phép", "",
        f"- Nguồn: {meta['source']}.", f"- Giấy phép: {meta['license']}. Bắt buộc ghi công trên giao diện; CSDL phái sinh công bố ra ngoài phải theo ODbL.",
        f"- Hệ tọa độ: {meta['crs']}. Lưới: ô {meta['cell_size_m']} m, vĩ độ tham chiếu {meta['ref_lat']} (trùng lưới pilot Cầu Giấy).",
        f"- Ghi chú hiệu lực: {meta['admin_note']}.", "",
        "## Kiểm chứng phạm vi", "",
        f"- Số ô có tâm nằm trong ranh giới thành phố: **{total:,}** ≈ {total * 0.01:,.0f} km² (mỗi ô ~0,01 km²).",
        f"- Diện tích vòng ranh giới ngoài tính từ OSM: {outer_km2:,.0f} km² (Hà Nội công bố ~3.359 km²).",
        f"- Đơn vị cấp xã trong OSM: {len(units)} ({sum(u['kind'] == 'phuong' for u in units)} phường, {sum(u['kind'] == 'xa' for u in units)} xã).",
        f"- Khớp mã phường trong CSDL Xanh24 (`wards`, {len(db_wards)} đơn vị): {len(db_wards & osm_slugs)}; có trong CSDL nhưng khác tên ở OSM: {', '.join(sorted(db_wards - osm_slugs)) or 'không'}.", "",
        "## Số ô theo trạng thái", "",
        "| Trạng thái | Số ô | Tỷ lệ | Ý nghĩa |", "|---|---:|---:|---|",
    ]
    meaning = {"eligible": "Có đường/lối đi công cộng — tính vào mẫu số", "pending_review": "Chưa có dữ liệu đường — chưa tính vào mẫu số, vẫn mở khóa được khi đến thật",
               "excluded": "Mặt nước — không tính, không mở khóa", "restricted": "Khu quân sự — không tính, không mở khóa"}
    for key in ("eligible", "pending_review", "excluded", "restricted"):
        lines.append(f"| `{key}` | {c.get(key, 0):,} | {100 * c.get(key, 0) / total:.1f}% | {meaning[key]} |")
    lines += ["", "## Số ô theo phường/xã", "", "| Đơn vị | Loại | Tổng ô | eligible | pending | excluded | restricted |", "|---|---|---:|---:|---:|---:|---:|"]
    for idx, unit in sorted(enumerate(units), key=lambda p: p[1]["name"]):
        k = per_unit.get(idx, collections.Counter())
        lines.append(f"| {unit['name']} (`{unit['slug']}`) | {unit['kind']} | {sum(k.values()):,} | {k['eligible']:,} | {k['pending_review']:,} | {k['excluded']:,} | {k['restricted']:,} |")
    k = per_unit.get(-1, collections.Counter())
    lines.append(f"| (Không thuộc đơn vị nào — dải ven ranh giới) | — | {sum(k.values()):,} | {k['eligible']:,} | {k['pending_review']:,} | {k['excluded']:,} | {k['restricted']:,} |")
    lines += ["", "## Hạn chế", "",
              "- `eligible` dựa trên đường OSM: thiếu đường ngõ nhỏ chưa vẽ thì ô bị xếp `pending_review`, không bị coi là bắt buộc.",
              "- Mặt nước nhỏ hơn một ô vẫn có thể khiến ô bị loại nếu phủ đúng tâm ô.",
              "- Khu hạn chế chỉ gồm `landuse=military` trong OSM; khu hạn chế khác do quản trị viên khai báo trong `/m4l/admin`.",
              "- Ranh giới do cộng đồng OSM số hóa, chưa phải dữ liệu pháp lý; cần đối chiếu nguồn chính thức trước khi công bố số liệu."]
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ghi {OUT_REPORT}", flush=True)


if __name__ == "__main__":
    main()
