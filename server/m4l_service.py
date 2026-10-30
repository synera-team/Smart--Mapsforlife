"""M4L 2.0 business rules: mood taxonomy, POI-mood links and filtered discovery.

Functions take plain values and raise ServiceError; m4l.py maps them to HTTP.
"""
import json
import math
import re
import secrets
import unicodedata

from db import IS_PG, get_db, get_setting, now, q
from geoutil import haversine_m

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CATEGORY = re.compile(r"[a-z0-9-]{1,40}")
MOOD_ICONS = ("compass", "laptop", "leaf", "heart", "bowl", "coffee", "music", "book", "tree", "camera", "star", "moon")
MOOD_STATUSES = ("active", "inactive")
MAX_LIMIT = 50
DEFAULT_LIMIT = 20
MAX_CURSOR = 10000
MAX_MOODS_PER_POI = 20

# Tunables; override any key with the JSON setting "m4l_config" (no restart needed).
DEFAULT_CONFIG = {
    "primary_area": "ha-noi",          # khu vực tính tiến độ mặc định; Cầu Giấy giữ làm pilot/test
    "cell_size_m": 100,                 # D7 — giá trị thử nghiệm
    "random_daily_quota": 10,           # lượt / 24 giờ trượt
    "random_cooldown_s": 3,
    "random_repeat_window_h": 24,
    "random_requires_mood_tag": True,   # không chọn mood: chỉ rút từ POI đã gắn mood (tránh gợi ý trụ sở hành chính)
    "unlock_max_accuracy_m": 50,
    "unlock_min_samples": 2,
    "unlock_sample_window_s": 120,
    "unlock_consistency_m": 75,
    "unlock_max_speed_mps": 40,
    "unlock_min_interval_s": 5,
    # Commerce (Phase 3/4). Business defaults pending approval — see docs/m4l/DECISION_LOG.md.
    "random_mode": "vip_pool",          # PDF §III: random() lấy từ pool đối tác VIP; "organic" = chỉ gợi ý tự nhiên
    "random_vip_fallback": "organic",   # pool VIP rỗng: "organic" (gợi ý tự nhiên, ghi rõ không tài trợ) | "none" (báo trống)
    "voucher_default_ttl_min": 60,      # PDF §I.4: đếm ngược 60 phút; mỗi mẫu voucher tự đặt được
    "kiosk_radius_m": 200,              # PDF §II.3: đối tác cách trạm ~200 m
    "kiosk_ticket_ttl_s": 180,
    "kiosk_tickets_per_min": 30,
    "kiosk_claim_window_s": 1800,       # nhận voucher trong 30 phút sau khi quét mã tại trạm
}

# Same public-visibility rule as /api/public/pois, plus a usable location.
VISIBLE = ("p.status='published' AND p.lat IS NOT NULL AND p.lng IS NOT NULL AND NOT EXISTS "
           "(SELECT 1 FROM cms_pins cp WHERE cp.poi_id=p.id AND "
           "(cp.active=0 OR cp.approved_at IS NULL OR cp.expires_at IS NULL OR cp.expires_at<=?))")


class ServiceError(Exception):
    def __init__(self, message, code="INVALID_PARAMETER", status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def norm(text):
    """Accent- and case-insensitive form, matching the search behaviour of the existing map."""
    text = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower()


def _int(value, name, low, high, default=None):
    if value in (None, ""):
        return default
    try:
        number = int(str(value).strip())
    except ValueError:
        raise ServiceError(f"Tham số {name} phải là số nguyên") from None
    if not low <= number <= high:
        raise ServiceError(f"Tham số {name} phải trong khoảng {low}–{high}")
    return number


def _coord(value, low, high):
    try:
        number = float(str(value).strip())
    except ValueError:
        raise ServiceError("Vị trí không hợp lệ", "INVALID_LOCATION") from None
    if not math.isfinite(number) or not low <= number <= high:
        raise ServiceError("Vị trí không hợp lệ", "INVALID_LOCATION")
    return number


def _text(value, name, max_len, required=False):
    text = str(value or "").strip()
    if required and not text:
        raise ServiceError(f"Cần nhập {name}")
    if len(text) > max_len:
        raise ServiceError(f"{name.capitalize()} tối đa {max_len} ký tự")
    return text


def first_image(images):
    try:
        items = json.loads(images or "[]") if isinstance(images, str) else (images or [])
    except ValueError:
        return ""
    for image in items if isinstance(items, list) else []:
        path = image.get("thumb") or image.get("url") if isinstance(image, dict) else image
        if isinstance(path, str) and (path.startswith("/uploads/") or path.startswith("https://")):
            return path
    return ""


def config():
    cfg = dict(DEFAULT_CONFIG)
    raw = get_setting("m4l_config")
    if isinstance(raw, dict):
        for key, value in raw.items():
            default = cfg.get(key)
            if key in cfg and isinstance(value, type(default)) and not (isinstance(value, bool) and not isinstance(default, bool)):
                cfg[key] = value
    return cfg


# ---------------------------------------------------------------- moods
def mood_public(row, poi_count=None):
    out = {"id": row["id"], "slug": row["slug"], "name": row["name"], "description": row["description"],
           "icon": row["icon"] if row["icon"] in MOOD_ICONS else "compass", "status": row["status"],
           "sort_order": row["sort_order"]}
    if poi_count is not None:
        out["poi_count"] = poi_count
    return out


def list_moods(include_inactive=False):
    where = "" if include_inactive else "WHERE m.status='active'"
    rows = q(f"SELECT m.*, (SELECT COUNT(*) FROM m4l_poi_moods pm JOIN pois p ON p.id=pm.poi_id "
             f"WHERE pm.mood_id=m.id AND {VISIBLE}) AS poi_count FROM m4l_moods m {where} "
             "ORDER BY m.sort_order, m.id", (now(),))
    return [mood_public(r, r["poi_count"]) for r in rows]


def _mood_fields(d, partial):
    out = {}
    if not partial or "name" in d:
        out["name"] = _text(d.get("name"), "tên mood", 80, required=True)
    if "description" in d or not partial:
        out["description"] = _text(d.get("description"), "mô tả", 300)
    if "icon" in d or not partial:
        icon = str(d.get("icon") or "compass")
        if icon not in MOOD_ICONS:
            raise ServiceError("Biểu tượng không hợp lệ")
        out["icon"] = icon
    if "status" in d or not partial:
        status = str(d.get("status") or "active")
        if status not in MOOD_STATUSES:
            raise ServiceError("Trạng thái phải là active hoặc inactive")
        out["status"] = status
    if "sort_order" in d or not partial:
        out["sort_order"] = _int(d.get("sort_order"), "sort_order", -1000, 1000, 0)
    return out


def create_mood(d, actor):
    slug = str(d.get("slug") or "").strip()
    if not 2 <= len(slug) <= 60 or not SLUG.fullmatch(slug):
        raise ServiceError("Slug chỉ gồm a-z, 0-9 và dấu gạch ngang (2–60 ký tự)")
    fields = _mood_fields(d, partial=False)
    if q("SELECT 1 FROM m4l_moods WHERE slug=?", (slug,), one=True):
        raise ServiceError("Slug đã tồn tại", "CONFLICT", 409)
    t = now()
    try:
        _execute("INSERT INTO m4l_moods(slug,name,description,icon,status,sort_order,created_by,created_at,updated_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?)", (slug, fields["name"], fields["description"], fields["icon"],
                                                fields["status"], fields["sort_order"], actor, t, t))
    except Exception:
        if q("SELECT 1 FROM m4l_moods WHERE slug=?", (slug,), one=True):
            raise ServiceError("Slug đã tồn tại", "CONFLICT", 409) from None
        raise
    return mood_public(q("SELECT * FROM m4l_moods WHERE slug=?", (slug,), one=True))


def update_mood(mood_id, d):
    row = q("SELECT * FROM m4l_moods WHERE id=?", (mood_id,), one=True)
    if not row:
        raise ServiceError("Không tìm thấy mood", "NOT_FOUND", 404)
    if "slug" in d and d["slug"] != row["slug"]:
        raise ServiceError("Không thể đổi slug của mood")
    fields = _mood_fields(d, partial=True)
    if not fields:
        raise ServiceError("Không có thay đổi")
    fields["updated_at"] = now()
    _execute(f"UPDATE m4l_moods SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), mood_id))
    return mood_public(q("SELECT * FROM m4l_moods WHERE id=?", (mood_id,), one=True)), dict(row)


# ---------------------------------------------------------------- discovery
def parse_discovery(args):
    mood = str(args.get("mood") or "").strip()
    if mood and (len(mood) > 60 or not SLUG.fullmatch(mood)):
        raise ServiceError("Mood không hợp lệ")
    category = str(args.get("category") or "").strip()
    if category and not CATEGORY.fullmatch(category):
        raise ServiceError("Danh mục không hợp lệ")
    text = _text(args.get("q"), "từ khóa", 100)
    lat, lng = args.get("lat"), args.get("lng")
    if (lat in (None, "")) != (lng in (None, "")):
        raise ServiceError("Cần cả vĩ độ và kinh độ", "INVALID_LOCATION")
    location = (_coord(lat, -90, 90), _coord(lng, -180, 180)) if lat not in (None, "") else None
    radius = _int(args.get("radius"), "radius", 100, 50000)
    if radius and not location:
        raise ServiceError("Lọc theo bán kính cần vị trí", "INVALID_LOCATION")
    return {"mood": mood, "category": category, "q": text, "location": location, "radius": radius,
            "limit": _int(args.get("limit"), "limit", 1, MAX_LIMIT, DEFAULT_LIMIT),
            "cursor": _int(args.get("cursor"), "cursor", 0, MAX_CURSOR, 0)}


def _completeness(row):
    return sum(bool(str(row[k] or "").strip()) for k in ("description", "hours", "phone", "address")) + bool(first_image(row["images"]))


def _mood_links(poi_ids):
    links = {}
    if not poi_ids:
        return links
    rows = q(f"SELECT pm.poi_id, pm.reason, m.slug, m.name FROM m4l_poi_moods pm JOIN m4l_moods m ON m.id=pm.mood_id "
             f"WHERE m.status='active' AND pm.poi_id IN ({','.join('?' * len(poi_ids))}) ORDER BY m.sort_order, m.id",
             tuple(poi_ids))
    for r in rows:
        links.setdefault(r["poi_id"], []).append(r)
    return links


def _candidates(params):
    """(mood row | None, [(row, distance_m | None, completeness)]) after every discovery filter, unsorted."""
    mood = None
    sql = ("SELECT p.*, c.name AS category_name, w.name AS ward_name FROM pois p "
           "LEFT JOIN categories c ON c.id=p.category LEFT JOIN wards w ON w.slug=p.ward_slug WHERE " + VISIBLE)
    args = [now()]
    if params["mood"]:
        mood = q("SELECT * FROM m4l_moods WHERE slug=? AND status='active'", (params["mood"],), one=True)
        if not mood:
            raise ServiceError("Không tìm thấy mood hoặc mood đã tắt", "MOOD_NOT_FOUND", 404)
        sql += " AND EXISTS (SELECT 1 FROM m4l_poi_moods pm WHERE pm.poi_id=p.id AND pm.mood_id=?)"
        args.append(mood["id"])
    if params["category"]:
        sql += " AND p.category=?"
        args.append(params["category"])
    rows = q(sql, args)

    if params["q"]:
        needle = norm(params["q"])
        rows = [r for r in rows if needle in norm(" ".join(str(r[k] or "") for k in
                ("name", "name_en", "address", "description", "tags", "category_name", "ward_name")))]
    location = params["location"]
    scored = []
    for r in rows:
        distance = haversine_m(location[0], location[1], r["lat"], r["lng"]) if location else None
        if params["radius"] and distance > params["radius"]:
            continue
        scored.append((r, distance, _completeness(r)))
    return mood, scored


def _item(r, distance, links, mood):
    own = links.get(r["id"], [])
    reasons = [link["reason"] for link in own if link["reason"] and (not mood or link["slug"] == mood["slug"])]
    return {
        "id": r["id"], "name": r["name"], "category": r["category"], "category_name": r["category_name"] or "",
        "ward_slug": r["ward_slug"], "ward_name": r["ward_name"] or "", "address": r["address"] or "",
        "description": (r["description"] or "")[:180], "hours": r["hours"] or "", "image": first_image(r["images"]),
        "lat": r["lat"], "lng": r["lng"], "distance_m": round(distance) if distance is not None else None,
        "moods": [link["slug"] for link in own], "reasons": reasons, "sponsored": False,
    }


def discover(params):
    mood, scored = _candidates(params)
    location = params["location"]
    if location:
        scored.sort(key=lambda s: (s[1], -s[2], s[0]["id"]))
    else:
        scored.sort(key=lambda s: (-s[2], -(s[0]["featured"] or 0), -(s[0]["published_at"] or 0), s[0]["id"]))

    start, limit = params["cursor"], params["limit"]
    page = scored[start:start + limit]
    links = _mood_links([s[0]["id"] for s in page])
    items = [_item(r, distance, links, mood) for r, distance, _ in page]
    next_cursor = start + limit if start + limit < len(scored) else None
    return {"mood": mood_public(mood) if mood else None, "items": items, "total": len(scored),
            "next_cursor": next_cursor, "sort": "distance" if location else "relevance"}


# ---------------------------------------------------------------- random (organic only until Phase 4 campaigns)
_rng = secrets.SystemRandom()


def random_pick(account_id, body):
    """One eligible POI, chosen uniformly from the filtered organic pool, under a per-account DB quota."""
    cfg = config()
    params = parse_discovery(body if isinstance(body, dict) else {})
    t = now()
    with transaction() as conn:
        if IS_PG:
            conn.execute("SELECT pg_advisory_xact_lock(?)", (4250000000 + account_id,))
        recent = conn.execute("SELECT COUNT(*) AS n, MAX(created_at) AS last FROM m4l_discovery_events "
                              "WHERE account_id=? AND channel='random' AND created_at>?", (account_id, t - 86400)).fetchone()
        if recent["last"] and t - recent["last"] < cfg["random_cooldown_s"]:
            raise ServiceError("Chờ một chút rồi lắc tiếp nhé", "COOLDOWN", 429)
        if recent["n"] >= cfg["random_daily_quota"]:
            raise ServiceError(f"Bạn đã dùng hết {cfg['random_daily_quota']} lượt khám phá ngẫu nhiên trong 24 giờ", "QUOTA_EXCEEDED", 429)
        import m4l_commerce as commerce
        mood, scored = _candidates(params)
        remaining = cfg["random_daily_quota"] - recent["n"]
        shown = {r["poi_id"] for r in conn.execute(
            "SELECT poi_id FROM m4l_discovery_events WHERE account_id=? AND channel='random' AND created_at>?",
            (account_id, t - cfg["random_repeat_window_h"] * 3600)).fetchall()}
        campaign = None
        vip = commerce.vip_pool(scored, params["location"]) if cfg["random_mode"] == "vip_pool" else []
        if vip:
            fresh = [v for v in vip if v[0]["poi_id"] not in shown]
            campaign, (row, distance, _) = _rng.choice(fresh or vip)
            choices = fresh or vip
            reason = (f"Chọn ngẫu nhiên trong {len(choices)} đối tác VIP đang chạy chiến dịch"
                      + (f" cho mood “{mood['name']}”" if mood else "") + ("" if fresh else " (bạn đã xem hết, nên có thể lặp lại)"))
        else:
            if cfg["random_mode"] == "vip_pool" and cfg["random_vip_fallback"] == "none":
                return {"item": None, "code": "NO_VIP_PARTNER", "message": "Hôm nay chưa có đối tác nào tham gia hộp mù",
                        "pool_size": 0, "remaining": remaining}
            pool = scored
            if not mood and cfg["random_requires_mood_tag"] and pool:
                tagged = {r["poi_id"] for r in conn.execute("SELECT DISTINCT pm.poi_id FROM m4l_poi_moods pm JOIN m4l_moods m ON m.id=pm.mood_id "
                                                             "WHERE m.status='active'").fetchall()}
                pool = [s for s in pool if s[0]["id"] in tagged]
            if not pool:
                return {"item": None, "code": "NO_ELIGIBLE_POI", "message": "Chưa có địa điểm phù hợp để gợi ý",
                        "pool_size": 0, "remaining": remaining}
            fresh = [s for s in pool if s[0]["id"] not in shown]
            choices = fresh or pool
            row, distance, _ = _rng.choice(choices)
            scope = (f"mood “{mood['name']}”" if mood else
                     "các địa điểm đã gắn mood" if cfg["random_requires_mood_tag"] else "mọi địa điểm đang công khai")
            reason = (f"Chọn ngẫu nhiên trong {len(choices)} địa điểm thuộc {scope}"
                      + ("" if fresh else " (bạn đã xem hết, nên có thể lặp lại)")
                      + (" · chưa có đối tác VIP phù hợp nên đây là gợi ý tự nhiên, không tài trợ" if cfg["random_mode"] == "vip_pool" else ""))
        conn.execute("INSERT INTO m4l_discovery_events(account_id,poi_id,mood_id,channel,sponsored,campaign_id,pool_size,reason,created_at) "
                     "VALUES(?,?,?,'random',?,?,?,?,?)", (account_id, row["id"], mood["id"] if mood else None, 1 if campaign else 0,
                                                          campaign["id"] if campaign else None, len(choices), reason, t))
        if campaign:
            commerce.impression(conn, {"account_id": account_id, "key": f"a{account_id}"}, campaign["id"], row["id"], "random")
    item = _item(row, distance, _mood_links([row["id"]]), mood)
    if campaign:
        item.update(sponsored=True, sponsor_label="Tài trợ", campaign_id=campaign["id"])
    commerce.attach_offers([item])
    return {"item": item, "reason": reason, "pool_size": len(choices), "remaining": remaining - 1,
            "mode": "vip" if campaign else "organic"}


# ---------------------------------------------------------------- admin: POI ↔ mood
def _scope_sql(scope):
    """scope None = all wards; otherwise restrict to the given ward slugs."""
    if scope is None:
        return "", []
    if not scope:
        return " AND 1=0", []
    return f" AND p.ward_slug IN ({','.join('?' * len(scope))})", sorted(scope)


def admin_pois(scope, text="", mood_id=None, limit=200):
    where, args = _scope_sql(scope)
    sql = ("SELECT p.id, p.name, p.address, p.category, p.ward_slug, p.status, w.name AS ward_name FROM pois p "
           "LEFT JOIN wards w ON w.slug=p.ward_slug WHERE p.status IN ('published','hidden')" + where)
    if mood_id:
        sql += " AND EXISTS (SELECT 1 FROM m4l_poi_moods pm WHERE pm.poi_id=p.id AND pm.mood_id=?)"
        args.append(mood_id)
    rows = q(sql + " ORDER BY p.name, p.id", args)
    if text:
        needle = norm(text)
        rows = [r for r in rows if needle in norm(f"{r['name']} {r['address']} {r['ward_name'] or ''}")]
    total = len(rows)
    rows = rows[:limit]
    links = {}
    if rows:
        for r in q(f"SELECT pm.poi_id, pm.mood_id, pm.reason FROM m4l_poi_moods pm WHERE pm.poi_id IN ({','.join('?' * len(rows))})",
                   tuple(r["id"] for r in rows)):
            links.setdefault(r["poi_id"], []).append({"id": r["mood_id"], "reason": r["reason"]})
    items = [{**dict(r), "moods": links.get(r["id"], [])} for r in rows]
    return {"items": items, "total": total}


def set_poi_moods(poi_id, payload, scope, actor):
    poi = q("SELECT id, ward_slug, status FROM pois WHERE id=?", (poi_id,), one=True)
    if not poi or poi["status"] == "archived":
        raise ServiceError("Không tìm thấy địa điểm", "NOT_FOUND", 404)
    if scope is not None and poi["ward_slug"] not in scope:
        raise ServiceError("Địa điểm nằm ngoài khu vực được giao", "FORBIDDEN", 403)
    moods = payload.get("moods") if isinstance(payload, dict) else None
    if not isinstance(moods, list) or len(moods) > MAX_MOODS_PER_POI:
        raise ServiceError(f"Cần danh sách moods (tối đa {MAX_MOODS_PER_POI})")
    wanted = {}
    for item in moods:
        if not isinstance(item, dict):
            raise ServiceError("Mỗi mood cần dạng {id, reason}")
        mood_id = _int(item.get("id"), "id", 1, 2 ** 31)
        if mood_id is None:
            raise ServiceError("Thiếu id mood")
        wanted[mood_id] = _text(item.get("reason"), "lý do", 200)
    if wanted:
        found = {r["id"] for r in q(f"SELECT id FROM m4l_moods WHERE id IN ({','.join('?' * len(wanted))})", tuple(wanted))}
        missing = sorted(set(wanted) - found)
        if missing:
            raise ServiceError(f"Mood không tồn tại: {missing}")
    before = [dict(r) for r in q("SELECT mood_id, reason FROM m4l_poi_moods WHERE poi_id=? ORDER BY mood_id", (poi_id,))]
    t = now()
    with transaction() as conn:
        conn.execute("DELETE FROM m4l_poi_moods WHERE poi_id=?", (poi_id,))
        for mood_id, reason in sorted(wanted.items()):
            conn.execute("INSERT INTO m4l_poi_moods(poi_id,mood_id,reason,created_by,created_at) VALUES(?,?,?,?,?)",
                         (poi_id, mood_id, reason, actor, t))
    after = [{"mood_id": k, "reason": v} for k, v in sorted(wanted.items())]
    return {"poi_id": poi_id, "moods": [{"id": a["mood_id"], "reason": a["reason"]} for a in after]}, before, after


# ---------------------------------------------------------------- db helpers
def _execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur


class transaction:
    """All-or-nothing writes on the request's connection (SQLite and Postgres)."""

    def __enter__(self):
        self.conn = get_db()
        if IS_PG:
            self._tx = self.conn.c.transaction()
            self._tx.__enter__()
        else:
            if self.conn.in_transaction:
                self.conn.commit()
            self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if IS_PG:
            return self._tx.__exit__(exc_type, exc, tb)
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        return False
