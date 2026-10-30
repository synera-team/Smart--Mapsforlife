"""M4L Fog of War: exploration areas, a stable lat/lng grid, server-side GPS validation and mystery pins.

Areas
  city   the whole of Hanoi, built offline from OpenStreetMap (tools/m4l_grid) and loaded by migration v3
  pilot  ward-based test areas (Cầu Giấy), grid generated from the `wards` table
Both use the grid in m4l_grid.py; with the same cell size and reference latitude the cell ids are identical,
so a pilot unlock is also a city unlock.

Cell status: eligible (counted in progress) · pending_review (reachability unknown — unlockable, not counted)
· excluded (water) · restricted (military / admin zones) — the last two are neither unlockable nor counted.
`base_status` keeps the source classification so admin zones can be applied and removed reversibly;
every reclassification bumps `classification_version` and is logged in m4l_grid_changes.

Only unlocked cells and the last accepted fix (rounded to ~11 m, one row per user) are stored —
never a location history.
"""
import json
import math

import m4l_grid as grid
from db import IS_PG, get_db, now, q
from geoutil import haversine_m, point_in_geom
from m4l_grid import UNLOCKABLE, grid_step
from m4l_service import SLUG, ServiceError, _int, _text, config, transaction

MAX_CELLS = 20000            # ward-based (pilot) areas only
MAX_VIEW_CELLS = 8000        # largest viewport answered cell-by-cell; bigger views get 1 km blocks
BLOCK = 10                   # cells per block side
PIN_STATUSES = ("draft", "published", "archived")
ZONE_KINDS = ("excluded", "restricted")
_cache = {}


# ---------------------------------------------------------------- grid
def cell_of(lat, lng, area):
    dlat, dlng = grid_step(area["cell_size_m"], area["ref_lat"])
    gx, gy = grid.cell_xy(lat, lng, dlat, dlng)
    return f"{gx}:{gy}", gx, gy


def cell_center(gx, gy, area):
    dlat, dlng = grid_step(area["cell_size_m"], area["ref_lat"])
    return (gy + .5) * dlat, (gx + .5) * dlng


def _ward_geoms(conn, slugs):
    if not slugs:
        return []
    rows = conn.execute(f"SELECT slug, geometry FROM wards WHERE geometry IS NOT NULL AND slug IN ({','.join('?' * len(slugs))})",
                        tuple(slugs)).fetchall()
    return [(r["slug"], json.loads(r["geometry"])) for r in rows]


def bulk(conn, sql, rows):
    """executemany on SQLite; pipelined executemany on the psycopg connection behind db._PgConn."""
    if hasattr(conn, "executemany"):
        conn.executemany(sql, rows)
    else:
        from db import _pg_sql
        with conn.c.cursor() as cur:
            cur.executemany(_pg_sql(sql), rows)


def build_grid(conn, area_id, ward_slugs, cell_size_m, version):
    """Write cells of a ward-based area for (area, version) on `conn`; returns (count, ref_lat). Caller owns the transaction."""
    geoms = _ward_geoms(conn, ward_slugs)
    if not geoms:
        raise ServiceError("Phường chưa có ranh giới bản đồ")
    ys = [y for _, g in geoms for r in grid.geometry_rings(g) for _, y in r]
    ref_lat = round((min(ys) + max(ys)) / 2, 1)
    dlat, dlng = grid_step(cell_size_m, ref_lat)
    cells = {}
    for slug, geom in geoms:
        for cell in grid.cells_in(grid.geometry_rings(geom), dlat, dlng):
            cells.setdefault(cell, slug)
    if len(cells) > MAX_CELLS:
        raise ServiceError("Quá nhiều ô; hãy tăng kích thước ô")
    bulk(conn, "INSERT INTO m4l_cells(area_id,grid_version,cell_id,gx,gy,status,base_status,unit_slug) "
               "VALUES(?,?,?,?,?,'eligible','eligible',?) ON CONFLICT DO NOTHING",
         [(area_id, version, f"{gx}:{gy}", gx, gy, slug) for (gx, gy), slug in cells.items()])
    return len(cells), ref_lat


# ---------------------------------------------------------------- areas
def area_public(row):
    dlat, dlng = grid_step(row["cell_size_m"], row["ref_lat"])
    return {"id": row["id"], "slug": row["slug"], "name": row["name"], "kind": row["kind"],
            "ward_slugs": json.loads(row["ward_slugs"] or "[]"), "cell_size_m": row["cell_size_m"], "ref_lat": row["ref_lat"],
            "dlat": dlat, "dlng": dlng, "grid_version": row["grid_version"], "classification_version": row["classification_version"],
            "eligible_cell_count": row["eligible_cell_count"], "status": row["status"]}


def get_area(slug=None, active_only=True):
    """Explicit slug, else the configured primary area, else the first active city, else the first active area."""
    cond = " AND status='active'" if active_only else ""
    if slug:
        row = q(f"SELECT * FROM m4l_areas WHERE slug=?{cond}", (slug,), one=True)
        if not row:
            raise ServiceError("Không tìm thấy khu vực khám phá", "AREA_NOT_FOUND", 404)
        return row
    return (q(f"SELECT * FROM m4l_areas WHERE slug=?{cond}", (config()["primary_area"],), one=True)
            or q(f"SELECT * FROM m4l_areas WHERE kind='city'{cond} ORDER BY id LIMIT 1", one=True)
            or q(f"SELECT * FROM m4l_areas WHERE 1=1{cond} ORDER BY id LIMIT 1", one=True))


def list_areas():
    return [area_public(r) for r in q("SELECT * FROM m4l_areas ORDER BY kind, id")]


def create_area(d, actor):
    slug = str(d.get("slug") or "").strip()
    if not 2 <= len(slug) <= 60 or not SLUG.fullmatch(slug):
        raise ServiceError("Slug chỉ gồm a-z, 0-9 và dấu gạch ngang (2–60 ký tự)")
    name = _text(d.get("name"), "tên khu vực", 80, required=True)
    wards = d.get("ward_slugs")
    if not isinstance(wards, list) or not 1 <= len(wards) <= 10 or not all(isinstance(w, str) and SLUG.fullmatch(w) for w in wards):
        raise ServiceError("Cần 1–10 mã phường hợp lệ")
    size = _int(d.get("cell_size_m"), "cell_size_m", 50, 500, config()["cell_size_m"])
    if q("SELECT 1 FROM m4l_areas WHERE slug=?", (slug,), one=True):
        raise ServiceError("Slug khu vực đã tồn tại", "CONFLICT", 409)
    t = now()
    with transaction() as c:
        c.execute("INSERT INTO m4l_areas(slug,name,kind,ward_slugs,cell_size_m,ref_lat,grid_version,classification_version,"
                  "eligible_cell_count,status,created_by,created_at,updated_at) VALUES(?,?,'pilot',?,?,0,1,1,0,'active',?,?,?)",
                  (slug, name, json.dumps(sorted(set(wards))), size, actor, t, t))
        area_id = c.execute("SELECT id FROM m4l_areas WHERE slug=?", (slug,)).fetchone()["id"]
        count, ref_lat = build_grid(c, area_id, sorted(set(wards)), size, 1)
        if not count:
            raise ServiceError("Không có ô nào nằm trong ranh giới phường")
        c.execute("UPDATE m4l_areas SET ref_lat=?, eligible_cell_count=? WHERE id=?", (ref_lat, count, area_id))
        log_change(c, area_id, 1, 1, "area.create", actor, {"cells": count, "ward_slugs": sorted(set(wards))})
    return area_public(q("SELECT * FROM m4l_areas WHERE id=?", (area_id,), one=True))


def regenerate_area(area_id, d, actor="system"):
    row = q("SELECT * FROM m4l_areas WHERE id=?", (area_id,), one=True)
    if not row:
        raise ServiceError("Không tìm thấy khu vực", "NOT_FOUND", 404)
    if row["kind"] == "city":
        raise ServiceError("Lưới toàn thành phố chỉ tạo lại bằng tools/m4l_grid và migration có kiểm duyệt", "NOT_SUPPORTED")
    size = _int(d.get("cell_size_m"), "cell_size_m", 50, 500, row["cell_size_m"])
    version = row["grid_version"] + 1
    with transaction() as c:
        count, ref_lat = build_grid(c, area_id, json.loads(row["ward_slugs"]), size, version)
        c.execute("UPDATE m4l_areas SET cell_size_m=?, ref_lat=?, grid_version=?, eligible_cell_count=?, updated_at=? WHERE id=?",
                  (size, ref_lat, version, count, now(), area_id))
        log_change(c, area_id, version, row["classification_version"], "grid.regenerate", actor,
                   {"cell_size_m": [row["cell_size_m"], size], "cells": count, "note": "tiến độ tính theo lưới mới; ô của lưới cũ vẫn được lưu"})
    return area_public(q("SELECT * FROM m4l_areas WHERE id=?", (area_id,), one=True)), area_public(row)


def set_area_status(area_id, status):
    if status not in ("active", "inactive"):
        raise ServiceError("Trạng thái phải là active hoặc inactive")
    if not q("SELECT 1 FROM m4l_areas WHERE id=?", (area_id,), one=True):
        raise ServiceError("Không tìm thấy khu vực", "NOT_FOUND", 404)
    get_db().execute("UPDATE m4l_areas SET status=?, updated_at=? WHERE id=?", (status, now(), area_id))
    get_db().commit()
    return area_public(q("SELECT * FROM m4l_areas WHERE id=?", (area_id,), one=True))


def log_change(conn, area_id, grid_version, classification_version, action, actor, summary):
    conn.execute("INSERT INTO m4l_grid_changes(area_id,grid_version,classification_version,action,actor,summary,created_at) "
                 "VALUES(?,?,?,?,?,?,?)", (area_id, grid_version, classification_version, action, actor,
                                           json.dumps(summary, ensure_ascii=False), now()))


def changes(area_id):
    return [{**dict(r), "summary": json.loads(r["summary"] or "{}")} for r in
            q("SELECT * FROM m4l_grid_changes WHERE area_id=? ORDER BY id DESC LIMIT 100", (area_id,))]


# ---------------------------------------------------------------- cached aggregates (static per grid + classification version)
def _key(area):
    return area["id"], area["grid_version"], area["classification_version"]


def _aggregates(area):
    key = _key(area)
    if key not in _cache:
        args = (area["id"], area["grid_version"])
        totals = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) AS n FROM m4l_cells WHERE area_id=? AND grid_version=? GROUP BY status", args)}
        units = {}
        for r in q("SELECT unit_slug, status, COUNT(*) AS n FROM m4l_cells WHERE area_id=? AND grid_version=? GROUP BY unit_slug, status", args):
            units.setdefault(r["unit_slug"], {})[r["status"]] = r["n"]
        blocks = {(r["block_x"], r["block_y"]): (r["e"], r["p"], r["n"]) for r in q(
            f"SELECT gx/{BLOCK} AS block_x, gy/{BLOCK} AS block_y, SUM(CASE WHEN status='eligible' THEN 1 ELSE 0 END) AS e, "
            f"SUM(CASE WHEN status='pending_review' THEN 1 ELSE 0 END) AS p, COUNT(*) AS n "
            f"FROM m4l_cells WHERE area_id=? AND grid_version=? GROUP BY gx/{BLOCK}, gy/{BLOCK}", args)}
        b = q("SELECT MIN(gx) AS x0, MAX(gx) AS x1, MIN(gy) AS y0, MAX(gy) AS y1 FROM m4l_cells WHERE area_id=? AND grid_version=?", args, one=True)
        if len(_cache) > 16:
            _cache.clear()
        _cache[key] = {"totals": totals, "units": units, "blocks": blocks, "bounds": (b["x0"], b["y0"], b["x1"], b["y1"])}
    return _cache[key]


def unit_names():
    return {r["slug"]: (r["name"], r["kind"]) for r in q("SELECT slug, name, kind FROM m4l_units")} | \
           {r["slug"]: (r["name"], r["type"]) for r in q("SELECT slug, name, type FROM wards")}


# ---------------------------------------------------------------- progress
def _user_unlocks(account_id, area):
    return {r["cell_id"]: (r["status"], r["unit_slug"]) for r in q(
        "SELECT u.cell_id, c.status, c.unit_slug FROM m4l_user_unlocks u JOIN m4l_cells c ON c.area_id=u.area_id "
        "AND c.grid_version=u.grid_version AND c.cell_id=u.cell_id WHERE u.account_id=? AND u.area_id=? AND u.grid_version=?",
        (account_id, area["id"], area["grid_version"]))}


def unlocked_cells(account_id, area):
    return list(_user_unlocks(account_id, area))


def progress(account_id, area, breakdown=False):
    agg = _aggregates(area)
    mine = _user_unlocks(account_id, area)
    eligible = agg["totals"].get("eligible", 0)
    pending = agg["totals"].get("pending_review", 0)
    unlocked = sum(1 for st, _ in mine.values() if st == "eligible")
    out = {"area": {"slug": area["slug"], "name": area["name"], "kind": area["kind"]},
           "unlocked": unlocked, "eligible": eligible, "percentage": round(100.0 * unlocked / eligible, 4) if eligible else 0.0,
           "unlocked_pending": sum(1 for st, _ in mine.values() if st == "pending_review"), "pending_review": pending,
           "excluded": agg["totals"].get("excluded", 0), "restricted": agg["totals"].get("restricted", 0),
           # the denominator is only final when no cell is still waiting for a reachability decision
           "complete": pending == 0, "grid_version": area["grid_version"], "classification_version": area["classification_version"]}
    if breakdown:
        names = unit_names()
        per_unit = {}
        for status, unit in mine.values():
            if status == "eligible":
                per_unit[unit] = per_unit.get(unit, 0) + 1
        units = []
        for slug, counts in agg["units"].items():
            e = counts.get("eligible", 0)
            if not e:
                continue
            name, kind = names.get(slug, (slug or "Ngoài ranh giới phường/xã", ""))
            units.append({"slug": slug, "name": name, "kind": kind, "eligible": e, "unlocked": per_unit.get(slug, 0),
                          "percentage": round(100.0 * per_unit.get(slug, 0) / e, 4), "pending_review": counts.get("pending_review", 0)})
        out["units"] = sorted(units, key=lambda u: (-u["unlocked"], u["name"] or ""))
    return out


# ---------------------------------------------------------------- viewport
def parse_bbox(raw):
    try:
        w, s, e, n = (float(v) for v in str(raw).split(","))
    except ValueError:
        raise ServiceError("bbox cần dạng minLng,minLat,maxLng,maxLat", "INVALID_PARAMETER") from None
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ServiceError("bbox không hợp lệ", "INVALID_PARAMETER")
    return w, s, e, n


def view(area, bbox=None, level="auto", account_id=None):
    """Cells (or 1 km blocks) of the area inside the viewport — never the whole city cell list."""
    if level not in ("auto", "cells", "blocks"):
        raise ServiceError("level phải là auto, cells hoặc blocks")
    agg = _aggregates(area)
    if agg["bounds"][0] is None:
        return {"level": "cells", "cells": [], "unlocked": [], "block_size": BLOCK}
    dlat, dlng = grid_step(area["cell_size_m"], area["ref_lat"])
    bx0, by0, bx1, by1 = agg["bounds"]
    if bbox:
        w, s, e, n = bbox
        gx0, gy0 = max(math.floor(w / dlng), bx0), max(math.floor(s / dlat), by0)
        gx1, gy1 = min(math.floor(e / dlng), bx1), min(math.floor(n / dlat), by1)
    else:
        gx0, gy0, gx1, gy1 = bx0, by0, bx1, by1
    if gx0 > gx1 or gy0 > gy1:
        return {"level": "cells", "cells": [], "unlocked": [], "block_size": BLOCK}
    span = (gx1 - gx0 + 1) * (gy1 - gy0 + 1)
    if level == "cells" and span > MAX_VIEW_CELLS:
        raise ServiceError("Khung nhìn quá lớn để tải từng ô; hãy phóng to", "VIEWPORT_TOO_LARGE")
    level = level if level != "auto" else ("cells" if span <= MAX_VIEW_CELLS else "blocks")
    mine = _user_unlocks(account_id, area) if account_id else {}
    if level == "cells":
        rows = q("SELECT gx, gy, status FROM m4l_cells WHERE area_id=? AND grid_version=? AND gy BETWEEN ? AND ? AND gx BETWEEN ? AND ?",
                 (area["id"], area["grid_version"], gy0, gy1, gx0, gx1))
        cells = [[r["gx"], r["gy"], grid.STATUS_CODES[r["status"]]] for r in rows]
        unlocked = [cid for cid in mine if gx0 <= int(cid.split(":")[0]) <= gx1 and gy0 <= int(cid.split(":")[1]) <= gy1]
        return {"level": "cells", "cells": cells, "unlocked": unlocked, "block_size": BLOCK}
    per_block = {}
    for cid, (status, _) in mine.items():
        gx, gy = map(int, cid.split(":"))
        if status in UNLOCKABLE:
            per_block[(gx // BLOCK, gy // BLOCK)] = per_block.get((gx // BLOCK, gy // BLOCK), 0) + 1
    blocks = [[bx, by, e, p, n, per_block.get((bx, by), 0)] for (bx, by), (e, p, n) in agg["blocks"].items()
              if gx0 // BLOCK <= bx <= gx1 // BLOCK and gy0 // BLOCK <= by <= gy1 // BLOCK]
    return {"level": "blocks", "blocks": blocks, "unlocked": [], "block_size": BLOCK}


def boundary(area):
    """Display boundary + provenance. City: simplified OSM boundary; pilot: its ward polygons."""
    key = ("boundary", area["id"])
    if key not in _cache:
        src = q("SELECT boundary, meta FROM m4l_area_sources WHERE area_id=?", (area["id"],), one=True)
        if src:
            _cache[key] = {"boundary": json.loads(src["boundary"]), "meta": json.loads(src["meta"])}
        else:
            polys = []
            for _, geom in _ward_geoms(get_db(), json.loads(area["ward_slugs"] or "[]")):
                polys += [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            _cache[key] = {"boundary": {"type": "MultiPolygon", "coordinates": polys},
                           "meta": {"source": "Ranh giới phường trong CSDL Xanh24 (bảng wards)"}}
    return _cache[key]


# ---------------------------------------------------------------- GPS validation
def parse_samples(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 10:
        raise ServiceError("Cần 1–10 mẫu vị trí", "INVALID_LOCATION")
    samples = []
    for item in raw:
        if not isinstance(item, dict):
            raise ServiceError("Mẫu vị trí không hợp lệ", "INVALID_LOCATION")
        try:
            lat, lng, acc, t = (float(item["lat"]), float(item["lng"]), float(item["accuracy"]), float(item["t"]))
        except (KeyError, TypeError, ValueError):
            raise ServiceError("Mẫu vị trí cần lat, lng, accuracy, t", "INVALID_LOCATION") from None
        if not all(math.isfinite(v) for v in (lat, lng, acc, t)) or not -90 <= lat <= 90 or not -180 <= lng <= 180 or acc <= 0:
            raise ServiceError("Mẫu vị trí không hợp lệ", "INVALID_LOCATION")
        samples.append({"lat": lat, "lng": lng, "accuracy": acc, "t": t / 1000.0})  # client sends ms
    return sorted(samples, key=lambda s: s["t"])


def validate_samples(samples, cfg, now_ts, last):
    """Raise ServiceError(422) unless the samples describe one plausible, accurate position. Returns that position."""
    if len(samples) < cfg["unlock_min_samples"]:
        raise ServiceError(f"Cần ít nhất {cfg['unlock_min_samples']} lần đo vị trí", "INSUFFICIENT_SAMPLES", 422)
    worst = max(s["accuracy"] for s in samples)
    if worst > cfg["unlock_max_accuracy_m"]:
        raise ServiceError(f"Vị trí chưa đủ chính xác (sai số {round(worst)} m > {cfg['unlock_max_accuracy_m']} m). "
                           "Hãy ra chỗ thoáng, bật định vị chính xác cao rồi thử lại.", "LOCATION_TOO_INACCURATE", 422)
    if samples[-1]["t"] - samples[0]["t"] > cfg["unlock_sample_window_s"]:
        raise ServiceError("Các lần đo cách nhau quá lâu", "LOCATION_INCONSISTENT", 422)
    first = samples[0]
    for prev, cur in zip(samples, samples[1:]):
        dist = haversine_m(prev["lat"], prev["lng"], cur["lat"], cur["lng"])
        if dist / max(cur["t"] - prev["t"], 1.0) > cfg["unlock_max_speed_mps"]:
            raise ServiceError("Di chuyển bất thường giữa các lần đo", "IMPLAUSIBLE_MOVEMENT", 422)
    if any(haversine_m(first["lat"], first["lng"], s["lat"], s["lng"]) > cfg["unlock_consistency_m"] for s in samples):
        raise ServiceError("Các lần đo không thống nhất, hãy đứng yên rồi thử lại", "LOCATION_INCONSISTENT", 422)
    point = samples[-1]
    if last and last["fix_at"] and now_ts - last["fix_at"] < 3600:
        dist = haversine_m(last["lat"], last["lng"], point["lat"], point["lng"])
        if dist / max(now_ts - last["fix_at"], 1) > cfg["unlock_max_speed_mps"]:
            raise ServiceError("Vị trí thay đổi quá nhanh so với lần trước", "IMPLAUSIBLE_MOVEMENT", 422)
    return point


NOT_COUNTED = {"excluded": "Ô này là mặt nước nên không tính khám phá", "restricted": "Ô này thuộc khu vực hạn chế nên không tính khám phá"}


def unlock(account_id, area, raw_samples):
    cfg = config()
    samples = parse_samples(raw_samples)
    t = now()
    with transaction() as c:
        if IS_PG:
            c.execute("SELECT pg_advisory_xact_lock(?)", (4240000000 + account_id,))
        last = c.execute("SELECT * FROM m4l_location_state WHERE account_id=?", (account_id,)).fetchone()
        if last and last["attempt_at"] and t - last["attempt_at"] < cfg["unlock_min_interval_s"]:
            raise ServiceError("Bạn thử quá nhanh, chờ vài giây", "RATE_LIMITED", 429)
        c.execute("INSERT INTO m4l_location_state(account_id,attempt_at) VALUES(?,?) "
                  "ON CONFLICT(account_id) DO UPDATE SET attempt_at=excluded.attempt_at", (account_id, t))
    # attempt is recorded even when validation fails, so rate limiting also covers rejected samples
    point = validate_samples(samples, cfg, t, last)
    cell_id, _, _ = cell_of(point["lat"], point["lng"], area)
    others = [a for a in q("SELECT * FROM m4l_areas WHERE status='active' AND id<>?", (area["id"],))]
    with transaction() as c:
        if IS_PG:
            c.execute("SELECT pg_advisory_xact_lock(?)", (4240000000 + account_id,))
        c.execute("UPDATE m4l_location_state SET lat=?, lng=?, accuracy=?, fix_at=? WHERE account_id=?",
                  (round(point["lat"], 4), round(point["lng"], 4), round(point["accuracy"]), t, account_id))
        cell = c.execute("SELECT status FROM m4l_cells WHERE area_id=? AND grid_version=? AND cell_id=?",
                         (area["id"], area["grid_version"], cell_id)).fetchone()
        if not cell:
            raise ServiceError(f"Vị trí của bạn nằm ngoài khu vực {area['name']}", "OUTSIDE_AREA", 422)
        if cell["status"] not in UNLOCKABLE:
            raise ServiceError(NOT_COUNTED[cell["status"]], "CELL_NOT_COUNTED", 422)
        already = c.execute("SELECT 1 FROM m4l_user_unlocks WHERE account_id=? AND area_id=? AND grid_version=? AND cell_id=?",
                            (account_id, area["id"], area["grid_version"], cell_id)).fetchone()
        rows = [(account_id, area["id"], area["grid_version"], cell_id, t)]
        for other in others:  # e.g. the Cầu Giấy pilot keeps counting alongside the city
            oid, _, _ = cell_of(point["lat"], point["lng"], other)
            hit = c.execute("SELECT status FROM m4l_cells WHERE area_id=? AND grid_version=? AND cell_id=?",
                            (other["id"], other["grid_version"], oid)).fetchone()
            if hit and hit["status"] in UNLOCKABLE:
                rows.append((account_id, other["id"], other["grid_version"], oid, t))
        for row in rows:
            c.execute("INSERT INTO m4l_user_unlocks(account_id,area_id,grid_version,cell_id,unlocked_at,validation_method) "
                      "VALUES(?,?,?,?,?,'gps') ON CONFLICT DO NOTHING", row)
    revealed = [p for p in pins_for(area, account_id) if p["unlocked"] and p["cell_id"] == cell_id]
    return {"unlocked": True, "already_unlocked": bool(already), "cell_id": cell_id, "cell_status": cell["status"],
            "counted": cell["status"] == "eligible", "progress": progress(account_id, area), "revealed_pins": revealed}


def forget_account(account_id):
    with transaction() as c:
        c.execute("DELETE FROM m4l_user_unlocks WHERE account_id=?", (account_id,))
        c.execute("DELETE FROM m4l_location_state WHERE account_id=?", (account_id,))


# ---------------------------------------------------------------- admin zones (restricted / excluded areas with a cited source)
def zones(area_id):
    return [{**dict(r), "geometry": json.loads(r["geometry"])} for r in q("SELECT * FROM m4l_zones WHERE area_id=? ORDER BY id DESC", (area_id,))]


def _zone_geometry(raw):
    geom = raw if isinstance(raw, dict) else None
    if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
        raise ServiceError("Cần GeoJSON Polygon hoặc MultiPolygon")
    try:
        rings = grid.geometry_rings(geom)
        points = sum(len(r) for r in rings)
        ok = rings and points <= 20000 and all(-180 <= x <= 180 and -90 <= y <= 90 for r in rings for x, y in r)
    except (TypeError, ValueError, KeyError):
        ok = False
    if not ok:
        raise ServiceError("Hình học vùng không hợp lệ (tối đa 20.000 đỉnh)")
    return geom


def create_zone(area, d, actor):
    kind = str(d.get("kind") or "")
    if kind not in ZONE_KINDS:
        raise ServiceError("Loại vùng phải là restricted hoặc excluded")
    name = _text(d.get("name"), "tên vùng", 120, required=True)
    source = _text(d.get("source"), "nguồn căn cứ", 300, required=True)
    note = _text(d.get("note"), "ghi chú", 500)
    geom = _zone_geometry(d.get("geometry"))
    t = now()
    get_db().execute("INSERT INTO m4l_zones(area_id,name,kind,geometry,source,note,active,created_by,created_at,updated_at) "
                     "VALUES(?,?,?,?,?,?,1,?,?,?)", (area["id"], name, kind, json.dumps(geom), source, note, actor, t, t))
    get_db().commit()
    zone = q("SELECT * FROM m4l_zones WHERE area_id=? ORDER BY id DESC LIMIT 1", (area["id"],), one=True)
    return dict(zone), reclassify(area, actor, f"zone.create:{zone['id']}")


def set_zone_active(zone_id, active, actor):
    zone = q("SELECT * FROM m4l_zones WHERE id=?", (zone_id,), one=True)
    if not zone:
        raise ServiceError("Không tìm thấy vùng", "NOT_FOUND", 404)
    get_db().execute("UPDATE m4l_zones SET active=?, updated_at=? WHERE id=?", (1 if active else 0, now(), zone_id))
    get_db().commit()
    area = q("SELECT * FROM m4l_areas WHERE id=?", (zone["area_id"],), one=True)
    return dict(q("SELECT * FROM m4l_zones WHERE id=?", (zone_id,), one=True)), reclassify(area, actor, f"zone.{'enable' if active else 'disable'}:{zone_id}")


def reclassify(area, actor, action):
    """Recompute cell status = base status overridden by active zones; bump classification_version and log counts."""
    before = dict(_aggregates(area)["totals"])
    dlat, dlng = grid_step(area["cell_size_m"], area["ref_lat"])
    active = q("SELECT * FROM m4l_zones WHERE area_id=? AND active=1 ORDER BY CASE kind WHEN 'excluded' THEN 0 ELSE 1 END, id", (area["id"],))
    version = area["classification_version"] + 1
    with transaction() as c:
        c.execute("UPDATE m4l_cells SET status=base_status WHERE area_id=? AND grid_version=? AND status<>base_status",
                  (area["id"], area["grid_version"]))
        for zone in active:
            cells = grid.cells_in(grid.geometry_rings(json.loads(zone["geometry"])), dlat, dlng)
            bulk(c, "UPDATE m4l_cells SET status=? WHERE area_id=? AND grid_version=? AND cell_id=?",
                 [(zone["kind"], area["id"], area["grid_version"], f"{gx}:{gy}") for gx, gy in cells])
        eligible = c.execute("SELECT COUNT(*) AS n FROM m4l_cells WHERE area_id=? AND grid_version=? AND status='eligible'",
                             (area["id"], area["grid_version"])).fetchone()["n"]
        c.execute("UPDATE m4l_areas SET classification_version=?, eligible_cell_count=?, updated_at=? WHERE id=?",
                  (version, eligible, now(), area["id"]))
        after = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM m4l_cells WHERE area_id=? AND grid_version=? "
                                                        "GROUP BY status", (area["id"], area["grid_version"])).fetchall()}
        log_change(c, area["id"], area["grid_version"], version, action, actor, {"before": before, "after": after, "active_zones": len(active)})
    return {"classification_version": version, "before": before, "after": after}


# ---------------------------------------------------------------- inspection
def inspect(lat, lng):
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ServiceError("Tọa độ không hợp lệ", "INVALID_LOCATION")
    names = unit_names()
    areas = []
    for area in q("SELECT * FROM m4l_areas ORDER BY kind, id"):
        cell_id, gx, gy = cell_of(lat, lng, area)
        row = q("SELECT status, base_status, unit_slug FROM m4l_cells WHERE area_id=? AND grid_version=? AND cell_id=?",
                (area["id"], area["grid_version"], cell_id), one=True)
        center = cell_center(gx, gy, area)
        areas.append({"area": area["slug"], "area_status": area["status"], "grid_version": area["grid_version"], "cell_id": cell_id,
                      "cell_center": [round(center[0], 6), round(center[1], 6)], "in_area": bool(row),
                      "status": row["status"] if row else None, "base_status": row["base_status"] if row else None,
                      "unit": {"slug": row["unit_slug"], "name": names.get(row["unit_slug"], (None,))[0]} if row and row["unit_slug"] else None})
    ward = next((r["slug"] for r in q("SELECT slug, geometry FROM wards WHERE geometry IS NOT NULL")
                 if point_in_geom(lng, lat, json.loads(r["geometry"]))), None)
    return {"lat": lat, "lng": lng, "xanh24_ward": ward, "areas": areas}


def stats(area):
    agg = _aggregates(area)
    names = unit_names()
    args = (area["id"], area["grid_version"])
    explorers = q("SELECT COUNT(DISTINCT account_id) AS n, COUNT(*) AS rows FROM m4l_user_unlocks WHERE area_id=? AND grid_version=?", args, one=True)
    covered = q("SELECT COUNT(DISTINCT u.cell_id) AS n FROM m4l_user_unlocks u JOIN m4l_cells c ON c.area_id=u.area_id AND c.grid_version=u.grid_version "
                "AND c.cell_id=u.cell_id WHERE u.area_id=? AND u.grid_version=? AND c.status='eligible'", args, one=True)["n"]
    per_unit = {r["unit_slug"]: (r["cells"], r["users"]) for r in q(
        "SELECT c.unit_slug, COUNT(DISTINCT u.cell_id) AS cells, COUNT(DISTINCT u.account_id) AS users FROM m4l_user_unlocks u "
        "JOIN m4l_cells c ON c.area_id=u.area_id AND c.grid_version=u.grid_version AND c.cell_id=u.cell_id "
        "WHERE u.area_id=? AND u.grid_version=? AND c.status='eligible' GROUP BY c.unit_slug", args)}
    eligible = agg["totals"].get("eligible", 0)
    units = [{"slug": slug, "name": names.get(slug, (slug or "Ngoài ranh giới phường/xã",))[0], "cells": sum(c.values()),
              **{k: c.get(k, 0) for k in ("eligible", "pending_review", "excluded", "restricted")},
              "covered": per_unit.get(slug, (0, 0))[0], "explorers": per_unit.get(slug, (0, 0))[1]}
             for slug, c in agg["units"].items()]
    return {"area": area_public(area), "totals": agg["totals"], "cells": sum(agg["totals"].values()),
            "explorers": explorers["n"], "unlock_records": explorers["rows"], "covered_eligible": covered,
            "coverage_percentage": round(100.0 * covered / eligible, 4) if eligible else 0.0,
            "units": sorted(units, key=lambda u: u["name"] or ""), "meta": boundary(area)["meta"]}


# ---------------------------------------------------------------- mystery pins
VISIBLE_POI = ("SELECT id, name, address, lat, lng FROM pois p WHERE p.id=? AND p.status='published' AND NOT EXISTS "
               "(SELECT 1 FROM cms_pins cp WHERE cp.poi_id=p.id AND "
               "(cp.active=0 OR cp.approved_at IS NULL OR cp.expires_at IS NULL OR cp.expires_at<=?))")


def pins_for(area, account_id=None, bbox=None):
    """Published pins of the area (optionally inside bbox). Locked pins expose only their teaser and the cell centre."""
    unlocked = set(unlocked_cells(account_id, area)) if account_id else set()
    sql, args = "SELECT * FROM m4l_mystery_pins WHERE area_id=? AND status='published'", [area["id"]]
    if bbox:
        pad_lat, pad_lng = grid_step(area["cell_size_m"], area["ref_lat"])
        sql += " AND lng BETWEEN ? AND ? AND lat BETWEEN ? AND ?"
        args += [bbox[0] - pad_lng, bbox[2] + pad_lng, bbox[1] - pad_lat, bbox[3] + pad_lat]
    out = []
    for row in q(sql + " ORDER BY id LIMIT 500", args):
        poi = q(VISIBLE_POI, (row["poi_id"], now()), one=True) if row["poi_id"] else None
        if row["poi_id"] and not poi:
            continue  # linked place no longer public
        cell_id, gx, gy = cell_of(row["lat"], row["lng"], area)
        center = cell_center(gx, gy, area)
        pin = {"id": row["id"], "teaser": row["teaser"], "cell_id": cell_id, "unlocked": cell_id in unlocked,
               "lat": round(center[0], 6), "lng": round(center[1], 6)}
        if pin["unlocked"]:
            pin.update(lat=row["lat"], lng=row["lng"], reveal_title=row["reveal_title"], reveal_text=row["reveal_text"],
                       poi=dict(poi) if poi else None)
        out.append(pin)
    return out


def pin_unit(area, lat, lng):
    cell_id, _, _ = cell_of(lat, lng, area)
    row = q("SELECT status, unit_slug FROM m4l_cells WHERE area_id=? AND grid_version=? AND cell_id=?",
            (area["id"], area["grid_version"], cell_id), one=True)
    return row


def _pin_fields(d, area, partial):
    out = {}
    if "poi_id" in d:
        out["poi_id"] = _int(d.get("poi_id"), "poi_id", 1, 2 ** 31)
        if out["poi_id"]:
            poi = q(VISIBLE_POI, (out["poi_id"], now()), one=True)
            if not poi:
                raise ServiceError("Địa điểm liên kết không tồn tại hoặc chưa công khai")
            if d.get("lat") in (None, "") and d.get("lng") in (None, ""):
                d = {**d, "lat": poi["lat"], "lng": poi["lng"]}
    if not partial or "lat" in d or "lng" in d:
        try:
            lat, lng = float(d.get("lat")), float(d.get("lng"))
        except (TypeError, ValueError):
            raise ServiceError("Cần tọa độ ghim hợp lệ", "INVALID_LOCATION") from None
        cell = pin_unit(area, lat, lng)
        if not cell:
            raise ServiceError("Tọa độ ghim nằm ngoài khu vực khám phá", "OUTSIDE_AREA")
        if cell["status"] not in UNLOCKABLE:
            raise ServiceError("Không đặt ghim ở mặt nước hoặc khu vực hạn chế", "CELL_NOT_COUNTED")
        out.update(lat=lat, lng=lng)
    if not partial or "teaser" in d:
        out["teaser"] = _text(d.get("teaser"), "lời gợi ý", 120, required=True)
    for key, label, size in (("reveal_title", "tiêu đề mở khóa", 120), ("reveal_text", "nội dung mở khóa", 500)):
        if not partial or key in d:
            out[key] = _text(d.get(key), label, size)
    if not partial or "status" in d:
        status = str(d.get("status") or "draft")
        if status not in PIN_STATUSES:
            raise ServiceError("Trạng thái ghim không hợp lệ")
        out["status"] = status
    return out


def admin_pins(area_ids):
    if not area_ids:
        return []
    rows = q(f"SELECT * FROM m4l_mystery_pins WHERE area_id IN ({','.join('?' * len(area_ids))}) ORDER BY id DESC", tuple(area_ids))
    return [dict(r) for r in rows]


def create_pin(area, d, actor):
    fields = _pin_fields(d, area, partial=False)
    t = now()
    get_db().execute("INSERT INTO m4l_mystery_pins(area_id,lat,lng,poi_id,teaser,reveal_title,reveal_text,status,created_by,created_at,updated_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (area["id"], fields["lat"], fields["lng"], fields.get("poi_id"), fields["teaser"],
                                                        fields["reveal_title"], fields["reveal_text"], fields["status"], actor, t, t))
    get_db().commit()
    return dict(q("SELECT * FROM m4l_mystery_pins WHERE area_id=? ORDER BY id DESC LIMIT 1", (area["id"],), one=True))


def update_pin(pin, area, d):
    fields = _pin_fields(d, area, partial=True)
    if not fields:
        raise ServiceError("Không có thay đổi")
    fields["updated_at"] = now()
    get_db().execute(f"UPDATE m4l_mystery_pins SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), pin["id"]))
    get_db().commit()
    return dict(q("SELECT * FROM m4l_mystery_pins WHERE id=?", (pin["id"],), one=True))
