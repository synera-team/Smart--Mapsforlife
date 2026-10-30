"""Xanh24 Maps for Life — SQLite data layer.

Một file SQLite duy nhất (data/xanh24.db) để dễ triển khai trên máy chủ nhỏ hoặc
mini-PC tại UBND. WAL mode cho phép đọc song song khi kiosk truy cập nhiều.
"""
import decimal
import json
import os
import re
import sqlite3
import threading
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA_DIR = "/tmp/xanh24" if os.environ.get("VERCEL") else os.path.join(BASE_DIR, "data")
DATA_DIR = os.environ.get("XANH24_DATA_DIR", DEFAULT_DATA_DIR)
DB_PATH = os.environ.get("XANH24_DB", os.path.join(DATA_DIR, "xanh24.db"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT DEFAULT '',
  email TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  role TEXT NOT NULL CHECK(role IN ('S0','S1','CW')),
  wards TEXT DEFAULT '[]',
  active INTEGER DEFAULT 1,
  must_change_password INTEGER DEFAULT 0,
  created_at INTEGER, last_login INTEGER
);

CREATE TABLE IF NOT EXISTS wards(
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  short TEXT,
  type TEXT DEFAULT 'phuong',
  area_km2 REAL,
  geometry TEXT,
  hq TEXT,
  source TEXT,
  scan_image TEXT,
  info TEXT DEFAULT '{}',
  published INTEGER DEFAULT 1,
  updated_at INTEGER, updated_by TEXT
);

CREATE TABLE IF NOT EXISTS categories(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_en TEXT DEFAULT '',
  icon TEXT DEFAULT 'pin',
  color TEXT DEFAULT '#1E6FD9',
  sort INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pois(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  ward_slug TEXT,
  category TEXT,
  name TEXT NOT NULL,
  name_en TEXT DEFAULT '',
  address TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  website TEXT DEFAULT '',
  hours TEXT DEFAULT '',
  description TEXT DEFAULT '',
  lat REAL, lng REAL,
  images TEXT DEFAULT '[]',
  vr360 TEXT DEFAULT 'null',
  tags TEXT DEFAULT '',
  extra TEXT DEFAULT '{}',
  featured INTEGER DEFAULT 0,
  status TEXT DEFAULT 'published' CHECK(status IN ('published','hidden','archived')),
  version INTEGER DEFAULT 1,
  created_at INTEGER, updated_at INTEGER,
  published_at INTEGER, published_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_pois_ward ON pois(ward_slug);
CREATE INDEX IF NOT EXISTS idx_pois_cat ON pois(category);

CREATE TABLE IF NOT EXISTS revisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  poi_id INTEGER,
  action TEXT NOT NULL CHECK(action IN ('create','update','delete')),
  data TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','pending','approved','rejected','cancelled')),
  batch_id TEXT,
  ward_slug TEXT,
  submitted_by INTEGER, submitted_at INTEGER,
  reviewed_by INTEGER, reviewed_at INTEGER, review_note TEXT DEFAULT '',
  created_by INTEGER, created_at INTEGER, updated_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_rev_status ON revisions(status);

CREATE TABLE IF NOT EXISTS import_batches(
  id TEXT PRIMARY KEY,
  filename TEXT, created_by INTEGER, created_at INTEGER,
  total INTEGER DEFAULT 0, valid INTEGER DEFAULT 0,
  rows TEXT DEFAULT '[]', status TEXT DEFAULT 'preview'
);

CREATE TABLE IF NOT EXISTS ads(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  media_type TEXT DEFAULT 'image' CHECK(media_type IN ('image','video','html','url')),
  media_url TEXT DEFAULT '',
  html TEXT DEFAULT '',
  duration_sec INTEGER DEFAULT 10,
  start_at INTEGER, end_at INTEGER,
  priority INTEGER DEFAULT 0,
  target_devices TEXT DEFAULT '[]',
  target_wards TEXT DEFAULT '[]',
  link_poi INTEGER,
  status TEXT DEFAULT 'pending' CHECK(status IN ('draft','pending','published','rejected','archived')),
  created_by INTEGER, created_at INTEGER, updated_at INTEGER,
  approved_by INTEGER
);

CREATE TABLE IF NOT EXISTS devices(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  ward_slug TEXT,
  address TEXT DEFAULT '',
  lat REAL, lng REAL,
  bearing REAL DEFAULT 0,
  orientation TEXT DEFAULT 'auto',
  idle_timeout INTEGER,
  config TEXT DEFAULT '{}',
  notes TEXT DEFAULT '',
  active INTEGER DEFAULT 1,
  last_seen INTEGER, last_ip TEXT, user_agent TEXT, screen TEXT,
  location_mode TEXT DEFAULT 'auto',
  gps_lat REAL, gps_lng REAL, gps_acc REAL, gps_src TEXT, gps_at INTEGER,
  created_at INTEGER
);

CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS modules(
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  kind TEXT DEFAULT 'iframe' CHECK(kind IN ('iframe','link','builtin','api')),
  entry_url TEXT DEFAULT '',
  icon TEXT DEFAULT 'grid',
  color TEXT DEFAULT '#1E6FD9',
  placement TEXT DEFAULT 'kiosk_menu',
  enabled INTEGER DEFAULT 0,
  config TEXT DEFAULT '{}',
  sort INTEGER DEFAULT 0,
  version TEXT DEFAULT '1.0',
  updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS webhooks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL, events TEXT DEFAULT '["*"]', secret TEXT, active INTEGER DEFAULT 1,
  last_status TEXT, created_at INTEGER
);

CREATE TABLE IF NOT EXISTS api_keys(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, prefix TEXT, key_hash TEXT, scopes TEXT DEFAULT '["read"]',
  active INTEGER DEFAULT 1, created_by INTEGER, created_at INTEGER, last_used INTEGER
);

CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER, username TEXT, action TEXT, entity TEXT, entity_id TEXT,
  detail TEXT DEFAULT '{}', ip TEXT, at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit(at);

CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_code TEXT, session_id TEXT, type TEXT, poi_id INTEGER, ward_slug TEXT,
  data TEXT DEFAULT '{}', at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_events_at ON events(at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

CREATE TABLE IF NOT EXISTS transit_lines(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT 'bus' CHECK(kind IN ('metro','bus','brt')),
  code TEXT, name TEXT, color TEXT DEFAULT '#1E6FD9', operator TEXT DEFAULT '',
  status TEXT DEFAULT 'operating', info TEXT DEFAULT '', stops TEXT DEFAULT '[]',
  geometry TEXT, updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS transit_stops(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT DEFAULT 'bus', name TEXT, lat REAL, lng REAL, lines TEXT DEFAULT '[]',
  note TEXT DEFAULT '', verified INTEGER DEFAULT 0
);
"""


def now():
    return int(time.time())


def _find_db_url():
    """DATABASE_URL, POSTGRES_URL, hoặc biến *_URL bất kỳ trỏ tới Postgres (VD: STORAGE_URL do Vercel/Neon tạo)."""
    for k in ("DATABASE_URL", "POSTGRES_URL"):
        if os.environ.get(k, "").strip().startswith(("postgres://", "postgresql://")):
            return os.environ[k].strip()
    for k, v in sorted(os.environ.items()):
        if k.endswith("_URL") and "UNPOOLED" not in k and "NON_POOLING" not in k and v.strip().startswith(("postgres://", "postgresql://")):
            return v.strip()
    return ""


DATABASE_URL = _find_db_url()
IS_PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))

# Bảng lưu tệp tải lên trong CSDL — dùng khi chạy Postgres (VD: Vercel, ổ đĩa không bền)
MEDIA_SCHEMA = """
CREATE TABLE IF NOT EXISTS media_files(
  path TEXT PRIMARY KEY,
  mime TEXT,
  data BLOB,
  size INTEGER,
  created_at INTEGER
);
"""


# ---------------------------------------------------------------- Postgres (tuỳ chọn)
class _Row(dict):
    """Hàng kết quả: truy cập được theo tên cột r["col"] và theo vị trí r[0] như sqlite3.Row."""
    __slots__ = ("_vals",)

    def __init__(self, cols, vals):
        super().__init__(zip(cols, vals))
        self._vals = vals

    def __getitem__(self, k):
        return self._vals[k] if isinstance(k, int) else dict.__getitem__(self, k)


class _Cur:
    def __init__(self, rows, lastrowid=None):
        self._rows, self.lastrowid = rows, lastrowid

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _pg_sql(sql):
    """Chuyển câu lệnh SQLite sang Postgres: ? → %s, % → %%, LIKE → ILIKE (không phân biệt hoa thường như SQLite)."""
    out, quote = [], False
    for ch in sql:
        if ch == "'":
            quote = not quote
            out.append(ch)
        elif ch == "?" and not quote:
            out.append("%s")
        elif ch == "%":
            out.append("%%")
        else:
            out.append(ch)
    return re.sub(r"\bLIKE\b", "ILIKE", "".join(out))


def _pg_schema(sql):
    sql = re.sub(r"(?im)^\s*PRAGMA[^;]*;\s*$", "", sql)
    sql = re.sub(r"INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY", sql)
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql)
    sql = re.sub(r"\bBLOB\b", "BYTEA", sql)
    sql = re.sub(r"\bINTEGER\b", "BIGINT", sql)
    return sql


ID_TABLES = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\(\s*id INTEGER PRIMARY KEY AUTOINCREMENT", SCHEMA))


def _pg_val(v):
    if isinstance(v, bool):
        return int(v)
    return v


def _py_val(v):
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, memoryview):
        return bytes(v)
    return v


class _PgConn:
    def __init__(self):
        import psycopg  # pip install "psycopg[binary]"
        # prepare_threshold=None: tương thích PgBouncer / pooler của Neon, Supabase, Vercel Postgres
        self.c = psycopg.connect(DATABASE_URL, autocommit=True, prepare_threshold=None, connect_timeout=15)

    def execute(self, sql, args=()):
        s = sql.strip()
        if re.match(r"(?is)CREATE\s+(TABLE|INDEX)", s):
            t = re.match(r"(?is)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(\s*id\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", s)
            if t:
                ID_TABLES.add(t.group(1))  # bảng của module mở rộng
            s = _pg_schema(s)
            with self.c.cursor() as cur:
                cur.execute(s)
            return _Cur([])
        m = re.match(r"(?is)INSERT\s+INTO\s+(\w+)", s)
        ret = bool(m and m.group(1) in ID_TABLES and "RETURNING" not in s.upper())
        s = _pg_sql(s) + (" RETURNING id" if ret else "")
        with self.c.cursor() as cur:
            cur.execute(s, tuple(_pg_val(a) for a in (args or ())))
            rows, last = [], None
            if cur.description:
                cols = [d.name for d in cur.description]
                rows = [_Row(cols, [_py_val(v) for v in r]) for r in cur.fetchall()]
                if ret and rows:
                    last = rows[0][0]
            return _Cur(rows, last)

    def executescript(self, script):
        for stmt in script.split(";"):
            if stmt.strip():
                with self.c.cursor() as cur:
                    cur.execute(stmt)

    def commit(self):
        pass

    def close(self):
        try:
            self.c.close()
        except Exception:
            pass

    @property
    def closed(self):
        return self.c.closed


def connect():
    if IS_PG:
        return _PgConn()
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    conn = getattr(_local, "conn", None)
    if conn is not None and IS_PG and conn.closed:
        conn = None
    if conn is None:
        conn = connect()
        _local.conn = conn
    return conn


# Cột bổ sung ở các phiên bản sau — tự thêm vào cơ sở dữ liệu cũ khi khởi động
MIGRATIONS = {
    "devices": {"location_mode": "TEXT DEFAULT 'auto'", "gps_lat": "REAL", "gps_lng": "REAL", "gps_acc": "REAL",
                "gps_src": "TEXT", "gps_at": "INTEGER"},
}


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = connect()
    if IS_PG:
        conn.executescript(_pg_schema(SCHEMA + MEDIA_SCHEMA))
        for table, cols in MIGRATIONS.items():
            for col, typ in cols.items():
                conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {_pg_schema(typ)}")
        conn.close()
        return
    conn.executescript(SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, typ in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()


def store_media(rel_path, data, mime=""):
    """Khi dùng Postgres: lưu thêm tệp tải lên vào CSDL để không mất khi máy chủ khởi động lại."""
    if not IS_PG:
        return
    ex("INSERT INTO media_files(path,mime,data,size,created_at) VALUES(?,?,?,?,?) "
       "ON CONFLICT(path) DO UPDATE SET data=excluded.data, mime=excluded.mime, size=excluded.size",
       (rel_path, mime, data, len(data), now()))


def load_media(rel_path):
    if not IS_PG:
        return None
    r = q("SELECT mime, data FROM media_files WHERE path=?", (rel_path,), one=True)
    return (r["mime"], r["data"]) if r else None


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def ex(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def row2dict(r, json_fields=()):
    if r is None:
        return None
    d = dict(r)
    for k in json_fields:
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


POI_JSON = ("images", "vr360", "extra")


def get_setting(key, default=None):
    r = q("SELECT value FROM settings WHERE key=?", (key,), one=True)
    if not r:
        return default
    try:
        return json.loads(r["value"])
    except Exception:
        return r["value"]


def set_setting(key, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
       (key, json.dumps(value, ensure_ascii=False)))


def all_settings():
    out = {}
    for r in q("SELECT key,value FROM settings"):
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out
