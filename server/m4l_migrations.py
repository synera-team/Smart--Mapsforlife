"""Versioned, additive migrations for the M4L 2.0 tables.

Kept apart from db.SCHEMA so the legacy start-up path is unchanged while the
feature flag is off. SQLite databases are backed up (sqlite3 backup API, WAL-safe)
before any pending migration or downgrade runs.

    python server/m4l_migrations.py status
    python server/m4l_migrations.py backup
    python server/m4l_migrations.py migrate
    python server/m4l_migrations.py downgrade --to 0 --yes
"""
import gzip
import json
import os
import sqlite3
import sys
import time

import db
import m4l_grid as grid
from db import DATA_DIR, IS_PG, now

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
# Postgres INSERTs only return ids for tables registered here; the CREATE may have run in an earlier process.
db.ID_TABLES.update(("m4l_moods", "m4l_areas", "m4l_mystery_pins", "m4l_discovery_events", "m4l_zones", "m4l_grid_changes",
                     "m4l_campaigns", "m4l_voucher_templates", "m4l_vouchers", "m4l_kiosk_sessions", "m4l_events"))

# Mood taxonomy samples from the product brief. They are editable configuration,
# not places: no POI is created or linked by a migration.
DEFAULT_MOODS = (
    ("chay-deadline", "Góc chạy deadline", "Không gian yên tĩnh, ngồi lâu để làm việc hoặc học.", "laptop", 10),
    ("xa-stress", "Cần xả stress", "Nơi thư giãn, thoáng đãng để nạp lại năng lượng.", "leaf", 20),
    ("hen-ho", "Hẹn hò lãng mạn", "Địa điểm hợp cho buổi hẹn hai người.", "heart", 30),
    ("am-thuc-dem", "Ẩm thực đêm khuya", "Quán còn mở muộn cho những cơn đói đêm.", "bowl", 40),
)


def _seed_moods(conn):
    for slug, name, description, icon, order in DEFAULT_MOODS:
        conn.execute("INSERT INTO m4l_moods(slug,name,description,icon,status,sort_order,created_by,created_at,updated_at) "
                     "VALUES(?,?,?,?,'active',?,'migration',?,?) ON CONFLICT(slug) DO NOTHING",
                     (slug, name, description, icon, order, now(), now()))


def _seed_pilot_area(conn):
    """Cầu Giấy pilot (100 m cells) from the real ward boundary, written with the v2 columns only."""
    slug, size = "cau-giay", 100
    ward = conn.execute("SELECT name, geometry FROM wards WHERE slug=? AND geometry IS NOT NULL", (slug,)).fetchone()
    if not ward or conn.execute("SELECT 1 FROM m4l_areas WHERE slug=?", (slug,)).fetchone():
        return
    rings = grid.geometry_rings(json.loads(ward["geometry"]))
    ys = [y for r in rings for _, y in r]
    ref_lat = round((min(ys) + max(ys)) / 2, 1)
    cells = grid.cells_in(rings, *grid.grid_step(size, ref_lat))
    conn.execute("INSERT INTO m4l_areas(slug,name,ward_slugs,cell_size_m,ref_lat,grid_version,eligible_cell_count,status,created_by,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,1,?,'active','migration',?,?)", (slug, ward["name"], json.dumps([slug]), size, ref_lat, len(cells), now(), now()))
    area_id = conn.execute("SELECT id FROM m4l_areas WHERE slug=?", (slug,)).fetchone()["id"]
    for gx, gy in cells:
        conn.execute("INSERT INTO m4l_cells(area_id,grid_version,cell_id,gx,gy) VALUES(?,1,?,?,?)", (area_id, f"{gx}:{gy}", gx, gy))


# ---------------------------------------------------------------- v3: Hanoi-wide grid
CITY_DATA = os.environ.get("XANH24_M4L_CITY_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "m4l_data", "hanoi_grid_v1.json.gz"))


def _columns(conn, table):
    if IS_PG:
        return {r["name"] for r in conn.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_name=?", (table,)).fetchall()}
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _v3(conn):
    from m4l_exploration import bulk, log_change
    for table, col, decl in (("m4l_areas", "kind", "TEXT NOT NULL DEFAULT 'pilot'"),
                             ("m4l_areas", "classification_version", "INTEGER NOT NULL DEFAULT 1"),
                             ("m4l_cells", "status", "TEXT NOT NULL DEFAULT 'eligible'"),
                             ("m4l_cells", "base_status", "TEXT NOT NULL DEFAULT 'eligible'"),
                             ("m4l_cells", "unit_slug", "TEXT")):
        if col not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_m4l_cells_xy ON m4l_cells(area_id, grid_version, gy, gx)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_m4l_cells_unit ON m4l_cells(area_id, grid_version, unit_slug, status)")
    report = {"started_at": now(), "pilot_backfill": {}, "city": None}
    # pilot cells: attribute each cell to its ward (status stays 'eligible', as before)
    for area in conn.execute("SELECT * FROM m4l_areas WHERE kind='pilot'").fetchall():
        dlat, dlng = grid.grid_step(area["cell_size_m"], area["ref_lat"])
        for slug in json.loads(area["ward_slugs"] or "[]"):
            row = conn.execute("SELECT geometry FROM wards WHERE slug=? AND geometry IS NOT NULL", (slug,)).fetchone()
            if row:
                ids = [(slug, area["id"], area["grid_version"], f"{gx}:{gy}") for gx, gy in grid.cells_in(grid.geometry_rings(json.loads(row["geometry"])), dlat, dlng)]
                bulk(conn, "UPDATE m4l_cells SET unit_slug=? WHERE area_id=? AND grid_version=? AND cell_id=? AND unit_slug IS NULL", ids)
        report["pilot_backfill"][area["slug"]] = conn.execute("SELECT COUNT(*) AS n FROM m4l_cells WHERE area_id=? AND unit_slug IS NOT NULL",
                                                               (area["id"],)).fetchone()["n"]
    report["city"] = _load_city(conn, bulk, log_change)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"m4l-v3-report-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  + M4L v3: báo cáo migration {path}")


def _load_city(conn, bulk, log_change):
    if not os.path.exists(CITY_DATA):
        return {"skipped": f"không có tệp dữ liệu {CITY_DATA}"}
    with gzip.open(CITY_DATA, "rt", encoding="utf-8") as f:
        data = json.load(f)
    meta = data["meta"]
    if conn.execute("SELECT 1 FROM m4l_areas WHERE slug=?", (meta["slug"],)).fetchone():
        return {"skipped": "khu vực thành phố đã tồn tại"}
    units = data["units"]
    bulk(conn, "INSERT INTO m4l_units(slug,name,kind,osm_relation,area_km2,source) VALUES(?,?,?,?,?,'osm') ON CONFLICT(slug) DO NOTHING",
         [(u["slug"], u["name"], u["kind"], u["osm_relation"], u["area_km2"]) for u in units])
    counts = meta["counts"]
    t = now()
    conn.execute("INSERT INTO m4l_areas(slug,name,kind,ward_slugs,cell_size_m,ref_lat,grid_version,classification_version,eligible_cell_count,"
                 "status,created_by,created_at,updated_at) VALUES(?,?,'city','[]',?,?,1,1,?,'active','migration',?,?)",
                 (meta["slug"], "Hà Nội", meta["cell_size_m"], meta["ref_lat"], counts.get("eligible", 0), t, t))
    area_id = conn.execute("SELECT id FROM m4l_areas WHERE slug=?", (meta["slug"],)).fetchone()["id"]
    conn.execute("INSERT INTO m4l_area_sources(area_id,boundary,meta,imported_at) VALUES(?,?,?,?)",
                 (area_id, json.dumps(data["boundary"]), json.dumps(meta, ensure_ascii=False), t))
    status_of = grid.STATUS_FROM_CODE
    rows = []
    for gy, runs in data["rows"]:
        for gx0, n, code, unit in runs:
            st, slug = status_of[code], units[unit]["slug"] if unit >= 0 else None
            rows += [(area_id, f"{gx}:{gy}", gx, gy, st, st, slug) for gx in range(gx0, gx0 + n)]
    bulk(conn, "INSERT INTO m4l_cells(area_id,grid_version,cell_id,gx,gy,status,base_status,unit_slug) VALUES(?,1,?,?,?,?,?,?)", rows)
    log_change(conn, area_id, 1, 1, "area.import", "migration", {"cells": len(rows), "counts": counts, "source": meta["source"],
                                                                 "osm_timestamp": meta["osm_timestamp"], "license": meta["license"]})
    # carry pilot progress over: same cell size and reference latitude ⇒ same cell ids
    carried = {}
    for pilot in conn.execute("SELECT * FROM m4l_areas WHERE kind='pilot' AND cell_size_m=? AND ref_lat=?",
                              (meta["cell_size_m"], meta["ref_lat"])).fetchall():
        old = conn.execute("SELECT u.account_id, u.cell_id, u.unlocked_at FROM m4l_user_unlocks u JOIN m4l_cells c ON c.area_id=? "
                           "AND c.grid_version=1 AND c.cell_id=u.cell_id WHERE u.area_id=? AND u.grid_version=?",
                           (area_id, pilot["id"], pilot["grid_version"])).fetchall()
        bulk(conn, "INSERT INTO m4l_user_unlocks(account_id,area_id,grid_version,cell_id,unlocked_at,validation_method) "
                   "VALUES(?,?,1,?,?,?) ON CONFLICT DO NOTHING",
             [(r["account_id"], area_id, r["cell_id"], r["unlocked_at"], f"migrated:{pilot['slug']}") for r in old])
        total = conn.execute("SELECT COUNT(*) AS n FROM m4l_user_unlocks WHERE area_id=?", (pilot["id"],)).fetchone()["n"]
        carried[pilot["slug"]] = {"carried": len(old), "kept_in_pilot_only": total - len(old)}
    if carried:
        log_change(conn, area_id, 1, 1, "unlocks.carry_over", "migration", carried)
    return {"area_id": area_id, "cells": len(rows), "counts": counts, "units": len(units), "pilot_unlocks": carried,
            "source": meta["source"], "license": meta["license"], "osm_timestamp": meta["osm_timestamp"]}


MIGRATIONS = (
    {
        "version": 1,
        "name": "moods",
        "up": (
            """CREATE TABLE IF NOT EXISTS m4l_moods(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              icon TEXT NOT NULL DEFAULT 'compass',
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_by TEXT DEFAULT '',
              created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_poi_moods(
              poi_id INTEGER NOT NULL REFERENCES pois(id) ON DELETE CASCADE,
              mood_id INTEGER NOT NULL REFERENCES m4l_moods(id) ON DELETE CASCADE,
              reason TEXT NOT NULL DEFAULT '',
              created_by TEXT DEFAULT '',
              created_at INTEGER,
              PRIMARY KEY(poi_id, mood_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_m4l_poi_moods_mood ON m4l_poi_moods(mood_id)",
        ),
        "data": _seed_moods,
        "down": ("DROP TABLE IF EXISTS m4l_poi_moods", "DROP TABLE IF EXISTS m4l_moods"),
    },
    {
        "version": 2,
        "name": "exploration_random",
        "up": (
            """CREATE TABLE IF NOT EXISTS m4l_areas(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              slug TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              ward_slugs TEXT NOT NULL DEFAULT '[]',
              cell_size_m INTEGER NOT NULL,
              ref_lat REAL NOT NULL,
              grid_version INTEGER NOT NULL DEFAULT 1,
              eligible_cell_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
              created_by TEXT DEFAULT '',
              created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_cells(
              area_id INTEGER NOT NULL REFERENCES m4l_areas(id) ON DELETE CASCADE,
              grid_version INTEGER NOT NULL,
              cell_id TEXT NOT NULL,
              gx INTEGER NOT NULL, gy INTEGER NOT NULL,
              PRIMARY KEY(area_id, grid_version, cell_id)
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_user_unlocks(
              account_id INTEGER NOT NULL,
              area_id INTEGER NOT NULL REFERENCES m4l_areas(id) ON DELETE CASCADE,
              grid_version INTEGER NOT NULL,
              cell_id TEXT NOT NULL,
              unlocked_at INTEGER NOT NULL,
              validation_method TEXT NOT NULL DEFAULT 'gps',
              PRIMARY KEY(account_id, area_id, grid_version, cell_id)
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_location_state(
              account_id INTEGER PRIMARY KEY,
              lat REAL, lng REAL, accuracy REAL,
              fix_at INTEGER, attempt_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_mystery_pins(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              area_id INTEGER NOT NULL REFERENCES m4l_areas(id) ON DELETE CASCADE,
              lat REAL NOT NULL, lng REAL NOT NULL,
              poi_id INTEGER REFERENCES pois(id) ON DELETE SET NULL,
              teaser TEXT NOT NULL,
              reveal_title TEXT NOT NULL DEFAULT '',
              reveal_text TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
              created_by TEXT DEFAULT '',
              created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_discovery_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              account_id INTEGER NOT NULL,
              poi_id INTEGER,
              mood_id INTEGER,
              channel TEXT NOT NULL,
              sponsored INTEGER NOT NULL DEFAULT 0,
              campaign_id INTEGER,
              pool_size INTEGER,
              reason TEXT DEFAULT '',
              created_at INTEGER NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_m4l_discovery_account ON m4l_discovery_events(account_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_m4l_pins_area ON m4l_mystery_pins(area_id, status)",
        ),
        "data": lambda conn: _seed_pilot_area(conn),
        "down": ("DROP TABLE IF EXISTS m4l_discovery_events", "DROP TABLE IF EXISTS m4l_mystery_pins",
                 "DROP TABLE IF EXISTS m4l_location_state", "DROP TABLE IF EXISTS m4l_user_unlocks",
                 "DROP TABLE IF EXISTS m4l_cells", "DROP TABLE IF EXISTS m4l_areas"),
    },
    {
        "version": 3,
        "name": "hanoi_city_grid",
        "up": (
            """CREATE TABLE IF NOT EXISTS m4l_units(
              slug TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              kind TEXT NOT NULL DEFAULT '',
              osm_relation INTEGER,
              area_km2 REAL,
              source TEXT NOT NULL DEFAULT ''
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_area_sources(
              area_id INTEGER PRIMARY KEY REFERENCES m4l_areas(id) ON DELETE CASCADE,
              boundary TEXT NOT NULL,
              meta TEXT NOT NULL DEFAULT '{}',
              imported_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_zones(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              area_id INTEGER NOT NULL REFERENCES m4l_areas(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              kind TEXT NOT NULL CHECK(kind IN ('excluded','restricted')),
              geometry TEXT NOT NULL,
              source TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              active INTEGER NOT NULL DEFAULT 1,
              created_by TEXT DEFAULT '',
              created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_grid_changes(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              area_id INTEGER NOT NULL,
              grid_version INTEGER NOT NULL,
              classification_version INTEGER NOT NULL,
              action TEXT NOT NULL,
              actor TEXT DEFAULT '',
              summary TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL
            )""",
        ),
        "data": lambda conn: _v3(conn),
        # Rollback removes the city area and everything attached to it (its unlocks and pins included);
        # pilot data stays. A backup is taken first — restore it if city progress must be recovered.
        "down": ("DELETE FROM m4l_user_unlocks WHERE area_id IN (SELECT id FROM m4l_areas WHERE kind='city')",
                 "DELETE FROM m4l_mystery_pins WHERE area_id IN (SELECT id FROM m4l_areas WHERE kind='city')",
                 "DELETE FROM m4l_cells WHERE area_id IN (SELECT id FROM m4l_areas WHERE kind='city')",
                 "DELETE FROM m4l_areas WHERE kind='city'",
                 "DROP TABLE IF EXISTS m4l_grid_changes", "DROP TABLE IF EXISTS m4l_zones",
                 "DROP TABLE IF EXISTS m4l_area_sources", "DROP TABLE IF EXISTS m4l_units",
                 "DROP INDEX IF EXISTS idx_m4l_cells_xy", "DROP INDEX IF EXISTS idx_m4l_cells_unit",
                 "UPDATE m4l_cells SET status='eligible'",
                 "ALTER TABLE m4l_cells DROP COLUMN unit_slug", "ALTER TABLE m4l_cells DROP COLUMN base_status",
                 "ALTER TABLE m4l_cells DROP COLUMN status", "ALTER TABLE m4l_areas DROP COLUMN classification_version",
                 "ALTER TABLE m4l_areas DROP COLUMN kind"),
    },
    {
        "version": 4,
        "name": "commerce_vouchers_kiosk",
        # Partners are the existing OWNER accounts (cms_accounts) and their assigned POI; kiosks are `devices`.
        # Nothing here charges money: campaigns carry contract data only, approval is manual.
        "up": (
            """CREATE TABLE IF NOT EXISTS m4l_campaigns(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              kind TEXT NOT NULL CHECK(kind IN ('mood_sponsor','vip_spin','kiosk_o2o')),
              name TEXT NOT NULL,
              partner_account_id INTEGER NOT NULL,
              poi_id INTEGER NOT NULL,
              mood_id INTEGER,
              center_lat REAL, center_lng REAL, radius_m INTEGER,
              starts_at INTEGER NOT NULL, ends_at INTEGER NOT NULL,
              priority INTEGER NOT NULL DEFAULT 0,
              package TEXT NOT NULL DEFAULT '',
              exclusive INTEGER NOT NULL DEFAULT 0,
              impression_cap INTEGER,
              status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','pending','approved','rejected','paused','ended')),
              is_demo INTEGER NOT NULL DEFAULT 0,
              review_note TEXT NOT NULL DEFAULT '', reviewed_by TEXT, reviewed_at INTEGER,
              created_by TEXT DEFAULT '', created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_voucher_templates(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id INTEGER NOT NULL UNIQUE REFERENCES m4l_campaigns(id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              benefit TEXT NOT NULL DEFAULT '',
              terms TEXT NOT NULL DEFAULT '',
              ttl_minutes INTEGER NOT NULL DEFAULT 60,
              issue_cap INTEGER NOT NULL,
              per_user_cap INTEGER NOT NULL DEFAULT 1,
              issued_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
              created_at INTEGER, updated_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_vouchers(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code TEXT NOT NULL UNIQUE,
              template_id INTEGER NOT NULL,
              campaign_id INTEGER NOT NULL,
              account_id INTEGER NOT NULL,
              poi_id INTEGER NOT NULL,
              source TEXT NOT NULL,
              kiosk_session_id INTEGER,
              idempotency_key TEXT,
              status TEXT NOT NULL DEFAULT 'issued' CHECK(status IN ('issued','redeemed','expired','revoked')),
              issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
              redeemed_at INTEGER, redeemed_by TEXT, redeem_ref TEXT,
              UNIQUE(account_id, idempotency_key)
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_kiosk_keys(
              device_id INTEGER PRIMARY KEY,
              key_hash TEXT NOT NULL,
              key_prefix TEXT NOT NULL,
              created_by TEXT DEFAULT '', created_at INTEGER,
              revoked_at INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_kiosk_sessions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              token_hash TEXT NOT NULL UNIQUE,
              device_id INTEGER NOT NULL,
              created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
              used_at INTEGER, account_id INTEGER
            )""",
            """CREATE TABLE IF NOT EXISTS m4l_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT UNIQUE,
              type TEXT NOT NULL,
              account_id INTEGER,
              campaign_id INTEGER, poi_id INTEGER, device_id INTEGER, voucher_id INTEGER,
              source TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_m4l_campaigns_live ON m4l_campaigns(kind, status, ends_at)",
            "CREATE INDEX IF NOT EXISTS idx_m4l_vouchers_account ON m4l_vouchers(account_id, issued_at)",
            "CREATE INDEX IF NOT EXISTS idx_m4l_vouchers_campaign ON m4l_vouchers(campaign_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_m4l_events_campaign ON m4l_events(campaign_id, type, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_m4l_events_at ON m4l_events(created_at)",
        ),
        "down": ("DROP TABLE IF EXISTS m4l_events", "DROP TABLE IF EXISTS m4l_kiosk_sessions", "DROP TABLE IF EXISTS m4l_kiosk_keys",
                 "DROP TABLE IF EXISTS m4l_vouchers", "DROP TABLE IF EXISTS m4l_voucher_templates", "DROP TABLE IF EXISTS m4l_campaigns"),
    },
)
LATEST = MIGRATIONS[-1]["version"]

LEDGER = """CREATE TABLE IF NOT EXISTS m4l_migrations(
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at INTEGER NOT NULL
)"""


def _begin(conn):
    if not IS_PG:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")


def applied_versions(conn=None):
    own = conn is None
    conn = conn or db.connect()
    try:
        return sorted(r[0] for r in conn.execute("SELECT version FROM m4l_migrations").fetchall())
    except Exception:
        return []
    finally:
        if own:
            conn.close()


def pending():
    have = set(applied_versions())
    return [m for m in MIGRATIONS if m["version"] not in have]


def backup_sqlite(label):
    """Consistent copy of the live SQLite file into DATA_DIR/backups. Returns the path, or None on Postgres."""
    if IS_PG or not os.path.exists(db.DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(db.DB_PATH))[0]
    path = os.path.join(BACKUP_DIR, f"{stem}-{label}-{time.strftime('%Y%m%d-%H%M%S')}.db")
    n = 1
    while os.path.exists(path):
        path = os.path.join(BACKUP_DIR, f"{stem}-{label}-{time.strftime('%Y%m%d-%H%M%S')}-{n}.db")
        n += 1
    src, dst = sqlite3.connect(db.DB_PATH), sqlite3.connect(path)
    try:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        src.close()
        dst.close()
    if result != "ok":
        raise RuntimeError(f"Bản sao lưu không toàn vẹn: {result}")
    return path


def migrate(log=print):
    todo = pending()
    if not todo:
        return []
    path = backup_sqlite(f"pre-m4l-v{todo[-1]['version']}")
    if path:
        log(f"  + M4L: đã sao lưu CSDL vào {path}")
    conn = db.connect()
    done = []
    try:
        conn.execute(LEDGER)
        conn.commit()
        for m in todo:
            _begin(conn)
            if m["version"] in applied_versions(conn):  # another worker got there first
                conn.commit()
                continue
            try:
                for stmt in m["up"]:
                    conn.execute(stmt)
                if m.get("data"):
                    m["data"](conn)
                conn.execute("INSERT INTO m4l_migrations(version,name,applied_at) VALUES(?,?,?) ON CONFLICT(version) DO NOTHING",
                             (m["version"], m["name"], now()))
                conn.commit()
            except Exception:
                if not IS_PG:
                    conn.rollback()
                raise
            done.append(m["version"])
            log(f"  + M4L migration v{m['version']} ({m['name']})")
    finally:
        conn.close()
    return done


def downgrade(to=0, log=print):
    """Drop M4L tables above version `to`. Legacy tables are never touched."""
    have = set(applied_versions())
    undo = [m for m in reversed(MIGRATIONS) if m["version"] in have and m["version"] > to]
    if not undo and to > 0:
        return []
    path = backup_sqlite(f"pre-m4l-down-v{to}")
    if path:
        log(f"  + M4L: đã sao lưu CSDL vào {path}")
    conn = db.connect()
    try:
        for m in undo:
            _begin(conn)
            for stmt in m["down"]:
                conn.execute(stmt)
            conn.execute("DELETE FROM m4l_migrations WHERE version=?", (m["version"],))
            conn.commit()
            log(f"  - M4L migration v{m['version']} ({m['name']}) đã gỡ")
        if to == 0:
            conn.execute("DROP TABLE IF EXISTS m4l_migrations")
            conn.commit()
    finally:
        conn.close()
    return [m["version"] for m in undo]


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        have = applied_versions()
        print(f"CSDL: {'Postgres' if IS_PG else db.DB_PATH}")
        print(f"Đã áp dụng: {have or 'chưa có'} · mới nhất: {LATEST} · đang chờ: {[m['version'] for m in pending()] or 'không'}")
    elif cmd == "backup":
        print(backup_sqlite("manual") or "Postgres: hãy dùng công cụ sao lưu của nhà cung cấp")
    elif cmd == "migrate":
        db.init_db()
        print(f"Đã áp dụng: {migrate() or 'không có migration mới'}")
    elif cmd == "downgrade":
        if "--yes" not in argv:
            print("Gỡ bảng M4L (dữ liệu mood sẽ mất, có sao lưu trước). Thêm --yes để xác nhận.")
            return 2
        to = int(argv[argv.index("--to") + 1]) if "--to" in argv else 0
        print(f"Đã gỡ: {downgrade(to) or 'không có'}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
