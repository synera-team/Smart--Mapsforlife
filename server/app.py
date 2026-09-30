"""Xanh24 — Maps for Life · máy chủ ứng dụng.

Chạy thử:  python server/app.py            (http://localhost:8024)
Sản xuất:  gunicorn -w 4 -b 0.0.0.0:8024 'server.wsgi:app'  (xem README)
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.request
from datetime import datetime

from flask import Flask, Response, abort, g, jsonify, redirect, request, send_file, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importer  # noqa: E402
import routing  # noqa: E402
from auth import (PERMISSIONS, ROLE_LABEL, audit, check_password, current_user, has_perm, hash_password,  # noqa: E402
                  issue_token, login_failed, login_ok, login_throttled, password_problem, public_user, require,
                  ward_allowed)
from db import (BASE_DIR, DATA_DIR, IS_PG, POI_JSON, UPLOAD_DIR, all_settings, ex, get_setting, init_db, load_media, now, q,  # noqa: E402
                row2dict, set_setting)
from geoutil import area_km2, bbox, centroid, haversine_m, point_in_geom, validate_geometry  # noqa: E402
from media import save_upload  # noqa: E402
from seed import seed_all  # noqa: E402

VERSION = "1.3.0"
WEB_DIR = os.path.join(BASE_DIR, "web")
DEFAULT_MAX_UPLOAD_MB = "4" if os.environ.get("VERCEL") else "200"
MAX_UPLOAD_MB = int(os.environ.get("XANH24_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB))

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.json.ensure_ascii = False
app.json.sort_keys = False

POI_FIELDS = ["name", "name_en", "category", "ward_slug", "address", "phone", "website", "hours", "description",
              "lat", "lng", "images", "vr360", "tags", "extra", "featured"]


def err(msg, code=400, **kw):
    return jsonify(error=msg, **kw), code


def body():
    return request.get_json(silent=True) or {}


# ======================================================================= helpers
def poi_dict(r):
    d = row2dict(r, POI_JSON)
    return d


def ward_geoms():
    cache = getattr(g, "_wg", None)
    if cache is None:
        cache = [(w["slug"], json.loads(w["geometry"])) for w in q("SELECT slug,geometry FROM wards WHERE geometry IS NOT NULL")]
        g._wg = cache
    return cache


def ward_for(lat, lng):
    if lat is None or lng is None:
        return None
    for slug, geom in ward_geoms():
        if point_in_geom(lng, lat, geom):
            return slug
    return None


def clean_poi_data(d, partial=False):
    """Chuẩn hoá & kiểm tra dữ liệu địa điểm. Trả (data, errors)."""
    out, errors = {}, []
    for k in POI_FIELDS:
        if k in d:
            out[k] = d[k]
    if not partial or "name" in out:
        if not str(out.get("name") or "").strip():
            errors.append("Tên địa điểm không được để trống")
        out["name"] = str(out.get("name") or "").strip()[:200]
    if not partial or "category" in out:
        if not q("SELECT 1 FROM categories WHERE id=?", (out.get("category"),), one=True):
            errors.append("Danh mục không hợp lệ")
    for k in ("lat", "lng"):
        if k in out:
            try:
                out[k] = float(out[k])
            except (TypeError, ValueError):
                errors.append("Toạ độ không hợp lệ")
    if "lat" in out and "lng" in out and not errors:
        if not (8 <= out["lat"] <= 24 and 102 <= out["lng"] <= 110):
            errors.append("Toạ độ nằm ngoài Việt Nam")
    elif not partial:
        errors.append("Thiếu toạ độ")
    if "images" in out:
        imgs = out["images"] or []
        if not isinstance(imgs, list):
            errors.append("Danh sách ảnh không hợp lệ")
        else:
            out["images"] = [i if isinstance(i, dict) else {"url": str(i), "thumb": str(i)} for i in imgs][:30]
    if "vr360" in out and out["vr360"]:
        v = out["vr360"]
        if not isinstance(v, dict) or v.get("type") not in ("pano", "embed", "video", "tour"):
            errors.append("Cấu hình VR360 không hợp lệ")
        elif v.get("type") == "embed" and not str(v.get("url", "")).startswith("https://"):
            errors.append("Link nhúng VR360 phải là https://")
    if "featured" in out:
        out["featured"] = 1 if out["featured"] in (1, True, "1", "true", "on") else 0
    for k in ("address", "phone", "website", "hours", "tags", "name_en"):
        if k in out:
            out[k] = str(out[k] or "").strip()[:500]
    if "description" in out:
        out["description"] = str(out["description"] or "")[:20000]
    if ("lat" in out and "lng" in out) and not out.get("ward_slug") and not errors:
        out["ward_slug"] = ward_for(out["lat"], out["lng"])
    return out, errors


def apply_revision(rev, reviewer):
    """Áp dụng yêu cầu thay đổi đã duyệt vào bảng pois. Trả poi_id."""
    data = json.loads(rev["data"]) if isinstance(rev["data"], str) else rev["data"]
    t = now()
    uname = reviewer["username"] if reviewer else "system"
    if rev["action"] == "create":
        cols = [k for k in POI_FIELDS if k in data]
        vals = [json.dumps(data[k], ensure_ascii=False) if k in POI_JSON else data[k] for k in cols]
        pid = ex(f"INSERT INTO pois({','.join(cols)},status,created_at,updated_at,published_at,published_by) VALUES({','.join('?' * len(cols))},'published',?,?,?,?)",
                 (*vals, t, t, t, uname))
        ex("UPDATE pois SET code=? WHERE id=?", (f"X24-{pid:05d}", pid))
        ex("UPDATE revisions SET poi_id=? WHERE id=?", (pid, rev["id"]))
        fire_webhook("poi.created", {"id": pid})
        return pid
    pid = rev["poi_id"]
    if not q("SELECT 1 FROM pois WHERE id=?", (pid,), one=True):
        raise ValueError("Địa điểm gốc không còn tồn tại")
    if rev["action"] == "update":
        cols = [k for k in POI_FIELDS if k in data]
        if cols:
            sets = ",".join(f"{k}=?" for k in cols)
            vals = [json.dumps(data[k], ensure_ascii=False) if k in POI_JSON else data[k] for k in cols]
            ex(f"UPDATE pois SET {sets},updated_at=?,published_at=?,published_by=?,version=version+1 WHERE id=?", (*vals, t, t, uname, pid))
        fire_webhook("poi.updated", {"id": pid})
    elif rev["action"] == "delete":
        ex("UPDATE pois SET status='archived',updated_at=? WHERE id=?", (t, pid))
        fire_webhook("poi.archived", {"id": pid})
    return pid


def fire_webhook(event, payload):
    try:
        hooks = q("SELECT * FROM webhooks WHERE active=1")
    except Exception:
        return
    if not hooks:
        return
    body_ = json.dumps({"event": event, "at": now(), "data": payload}, ensure_ascii=False).encode()

    def send(h):
        try:
            evs = json.loads(h["events"] or '["*"]')
            if "*" not in evs and event not in evs:
                return
            sig = hmac.new((h["secret"] or "").encode(), body_, hashlib.sha256).hexdigest()
            req = urllib.request.Request(h["url"], data=body_, method="POST",
                                         headers={"Content-Type": "application/json", "X-Xanh24-Event": event,
                                                  "X-Xanh24-Signature": "sha256=" + sig})
            with urllib.request.urlopen(req, timeout=6) as r:
                st = str(r.status)
        except Exception as e:  # noqa
            st = "ERR " + str(e)[:120]
        try:
            from db import connect
            c = connect(); c.execute("UPDATE webhooks SET last_status=? WHERE id=?", (st, h["id"])); c.commit(); c.close()
        except Exception:
            pass
    for h in hooks:
        threading.Thread(target=send, args=(dict(h),), daemon=True).start()


def public_settings():
    s = all_settings()
    keep = ["app_name", "app_short", "org_name", "copyright", "region_name", "idle_timeout", "idle_warning",
            "default_center", "default_zoom", "languages", "tiles", "transit", "kiosk", "public_base_url", "geocode"]
    out = {k: s.get(k) for k in keep}
    if out.get("geocode"):
        out["geocode"] = {k: v for k, v in out["geocode"].items() if k in ("enabled", "pick_hint")}
    ride = s.get("ride") or {}
    out["ride"] = {k: {kk: vv for kk, vv in v.items()} for k, v in ride.items() if v.get("enabled")}
    if out.get("kiosk"):
        out["kiosk"] = {k: v for k, v in out["kiosk"].items() if k != "admin_exit_pin"}
    return out


# ======================================================================= static
@app.after_request
def headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/admin")
@app.route("/admin/")
def admin_index():
    return send_from_directory(os.path.join(WEB_DIR, "admin"), "index.html")


@app.route("/uploads/<path:p>")
def uploads(p):
    full = os.path.join(UPLOAD_DIR, p)
    if not os.path.isfile(full) and IS_PG and ".." not in p:
        m = load_media(p)  # tệp lưu trong Postgres → ghi lại bộ nhớ đệm đĩa rồi phục vụ
        if not m:
            abort(404)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(m[1])
    resp = send_from_directory(UPLOAD_DIR, p, max_age=86400 * 30)
    return resp


@app.route("/go/<provider>")
def go(provider):
    return send_from_directory(WEB_DIR, "go.html")


@app.route("/<path:p>")
def static_files(p):
    full = os.path.join(WEB_DIR, p)
    if os.path.isdir(full):
        p = p.rstrip("/") + "/index.html"
    if not os.path.exists(os.path.join(WEB_DIR, p)):
        abort(404)
    max_age = 3600 if p.startswith(("vendor/", "assets/")) else 0
    return send_from_directory(WEB_DIR, p, max_age=max_age)


# ======================================================================= public API
@app.route("/api/health")
def health():
    return jsonify(ok=True, version=VERSION, time=now())


@app.route("/api/public/bootstrap")
def bootstrap():
    code = request.args.get("device")
    dev = None
    if code:
        d = q("SELECT * FROM devices WHERE code=? AND active=1", (code,), one=True)
        if d:
            dev = row2dict(d, ("config",))
            for k in ("last_ip", "user_agent", "notes"):
                dev.pop(k, None)
    cats = [dict(r) for r in q("SELECT id,name,name_en,icon,color FROM categories WHERE active=1 ORDER BY sort")]
    counts = {r["category"]: r["n"] for r in q("SELECT category,COUNT(*) n FROM pois WHERE status='published' GROUP BY category")}
    for c in cats:
        c["count"] = counts.get(c["id"], 0)
    mods = [row2dict(r, ("config",)) for r in q("SELECT key,name,description,kind,entry_url,icon,color,placement,config FROM modules WHERE enabled=1 ORDER BY sort")]
    wards = [dict(slug=r["slug"], name=r["name"], short=r["short"], type=r["type"], area_km2=r["area_km2"],
                  hq=json.loads(r["hq"] or "null"), info=json.loads(r["info"] or "{}"),
                  poi_count=r["n"]) for r in
             q("SELECT w.*, (SELECT COUNT(*) FROM pois p WHERE p.ward_slug=w.slug AND p.status='published') n FROM wards w WHERE published=1 ORDER BY short")]
    return jsonify(version=VERSION, data_version=data_version(), settings=public_settings(), device=dev, categories=cats, modules=mods, wards=wards,
                   server_time=now())


@app.route("/api/public/wards.geojson")
def wards_geojson():
    feats = []
    for r in q("SELECT slug,name,short,type,area_km2,geometry,hq FROM wards WHERE published=1 AND geometry IS NOT NULL"):
        geom = json.loads(r["geometry"])
        feats.append({"type": "Feature", "id": r["slug"],
                      "properties": {"slug": r["slug"], "name": r["name"], "short": r["short"], "type": r["type"],
                                     "area_km2": r["area_km2"], "center": centroid(geom)},
                      "geometry": geom})
    resp = jsonify(type="FeatureCollection", features=feats)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


def _public_poi(r, full=False):
    d = poi_dict(r)
    for k in ("published_by", "version", "status") if not full else ("published_by",):
        d.pop(k, None)
    if not full:
        d["images"] = d["images"][:1] if isinstance(d.get("images"), list) else []
        d["has_vr"] = bool(d.get("vr360"))
        d.pop("vr360", None)
        d["description"] = (d.get("description") or "")[:180]
        extra = d.pop("extra", {}) or {}
    return d


@app.route("/api/public/pois")
def public_pois():
    sql = "SELECT * FROM pois WHERE status='published'"
    args = []
    if request.args.get("ward"):
        sql += " AND ward_slug=?"; args.append(request.args["ward"])
    if request.args.get("category"):
        cats = request.args["category"].split(",")
        sql += f" AND category IN ({','.join('?' * len(cats))})"; args += cats
    if request.args.get("featured"):
        sql += " AND featured=1"
    sql += " ORDER BY featured DESC, name"
    rows = [_public_poi(r) for r in q(sql, args)]
    return jsonify(items=rows, total=len(rows))


@app.route("/api/public/pois/<int:pid>")
def public_poi(pid):
    r = q("SELECT * FROM pois WHERE id=? AND status='published'", (pid,), one=True)
    if not r:
        return err("Không tìm thấy địa điểm", 404)
    d = _public_poi(r, full=True)
    w = q("SELECT name FROM wards WHERE slug=?", (r["ward_slug"],), one=True)
    d["ward_name"] = w["name"] if w else None
    # điểm dừng giao thông gần nhất
    stops = []
    for s in q("SELECT * FROM transit_stops"):
        dist = haversine_m(r["lat"], r["lng"], s["lat"], s["lng"])
        if dist < 1500:
            stops.append(dict(id=s["id"], kind=s["kind"], name=s["name"], lat=s["lat"], lng=s["lng"],
                              lines=json.loads(s["lines"] or "[]"), distance=round(dist)))
    d["nearby_stops"] = sorted(stops, key=lambda x: x["distance"])[:6]
    return jsonify(d)


@app.route("/api/public/transit")
def public_transit():
    lines = [row2dict(r, ("stops", "geometry")) for r in q("SELECT * FROM transit_lines ORDER BY kind, code")]
    stops = [row2dict(r, ("lines",)) for r in q("SELECT * FROM transit_stops")]
    return jsonify(lines=lines, stops=stops)


@app.route("/api/public/ads")
def public_ads():
    code = request.args.get("device")
    dev = q("SELECT * FROM devices WHERE code=?", (code,), one=True) if code else None
    t = now()
    out = []
    for r in q("SELECT * FROM ads WHERE status='published' ORDER BY priority DESC, id"):
        if r["start_at"] and r["start_at"] > t:
            continue
        if r["end_at"] and r["end_at"] < t:
            continue
        td = json.loads(r["target_devices"] or "[]")
        tw = json.loads(r["target_wards"] or "[]")
        if td and (not dev or dev["code"] not in td):
            continue
        if tw and (not dev or dev["ward_slug"] not in tw):
            continue
        out.append(dict(id=r["id"], title=r["title"], media_type=r["media_type"], media_url=r["media_url"],
                        html=r["html"], duration_sec=r["duration_sec"], link_poi=r["link_poi"]))
    return jsonify(items=out)


@app.route("/api/public/route")
def public_route():
    try:
        f = [float(x) for x in request.args["from"].split(",")]
        t = [float(x) for x in request.args["to"].split(",")]
    except Exception:
        return err("Tham số from/to phải dạng lng,lat")
    mode = request.args.get("mode", "foot")
    lang = request.args.get("lang", "vi")
    res = routing.route(all_settings(), mode, f, t, lang)
    return jsonify(res)


@app.route("/api/public/reverse")
def public_reverse():
    """Thông tin một điểm bất kỳ: phường (theo ranh giới nội bộ) + địa chỉ (Nominatim/OSM)."""
    try:
        lat, lng = float(request.args["lat"]), float(request.args["lng"])
    except Exception:
        return err("Thiếu lat/lng")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return err("Toạ độ không hợp lệ")
    import geocode
    info = geocode.reverse(all_settings(), lat, lng, request.args.get("lang", "vi")) or {}
    resp = jsonify(lat=lat, lng=lng, ward_slug=ward_for(lat, lng), name=info.get("name", ""), address=info.get("address", ""),
                   road=info.get("road", ""), category=info.get("category", ""), type=info.get("type", ""), source="osm" if info else "none")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/api/public/geocode")
def public_geocode():
    """Tìm địa chỉ / địa điểm bất kỳ trong khu vực Hà Nội (không giới hạn các điểm đã nhập)."""
    import geocode
    q = (request.args.get("q") or "").strip()[:120]
    try:
        lat, lng = float(request.args.get("lat", 21.0278)), float(request.args.get("lng", 105.8342))
    except ValueError:
        lat, lng = 21.0278, 105.8342
    items = geocode.search(all_settings(), q, lat, lng, request.args.get("lang", "vi"))
    for it in items:
        it["ward_slug"] = ward_for(it["lat"], it["lng"])
    resp = jsonify(items=items)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/api/public/geolocate", methods=["POST"])
def public_geolocate():
    """Kiosk không có GPS gửi danh sách Wi-Fi xung quanh → trả toạ độ (giống cách Google Maps định vị)."""
    import geocode
    d = body()
    wifi = [w for w in (d.get("wifi") or []) if isinstance(w, dict)][:60]
    cells = [c for c in (d.get("cells") or []) if isinstance(c, dict)][:10]
    r = geocode.wifi_locate(all_settings(), wifi, cells)
    if not r:
        return err("Không xác định được vị trí từ Wi-Fi", 404)
    r["ward_slug"] = ward_for(r["lat"], r["lng"])
    return jsonify(r)


@app.route("/api/public/events", methods=["POST"])
def public_events():
    d = body()
    evs = d.get("events") if isinstance(d.get("events"), list) else [d]
    code = str(d.get("device") or "")[:40]
    sid = str(d.get("session") or "")[:40]
    t = now()
    n = 0
    for e in evs[:100]:
        typ = str(e.get("type") or "")[:40]
        if not typ:
            continue
        ex("INSERT INTO events(device_code,session_id,type,poi_id,ward_slug,data,at) VALUES(?,?,?,?,?,?,?)",
           (code, sid, typ, e.get("poi_id"), e.get("ward"), json.dumps(e.get("data") or {}, ensure_ascii=False)[:2000],
            int(e.get("at") or t)))
        n += 1
    return jsonify(ok=True, stored=n)


@app.route("/api/public/kiosk/unlock", methods=["POST"])
def kiosk_unlock():
    key = f"pin|{request.remote_addr}"
    wait = login_throttled(key)
    if wait:
        return err(f"Thử lại sau {wait} giây", 429)
    pin = str((get_setting("kiosk") or {}).get("admin_exit_pin") or "")
    if pin and hmac.compare_digest(pin, str(body().get("pin") or "")):
        login_ok(key)
        return jsonify(ok=True)
    login_failed(key)
    return err("Mã PIN không đúng", 403)


@app.route("/api/public/heartbeat", methods=["POST"])
def heartbeat():
    d = body()
    code = d.get("device")
    if code:
        ex("UPDATE devices SET last_seen=?, last_ip=?, user_agent=?, screen=? WHERE code=?",
           (now(), request.headers.get("X-Forwarded-For", request.remote_addr), request.headers.get("User-Agent", "")[:300],
            str(d.get("screen") or "")[:40], code))
        g = d.get("gps") or {}
        try:
            glat, glng = float(g["lat"]), float(g["lng"])
            gacc = float(g["acc"]) if g.get("acc") is not None else 9999.0
        except (KeyError, TypeError, ValueError):
            glat = None
        if glat is not None and -90 <= glat <= 90 and -180 <= glng <= 180:
            # Vị trí thực tế do thiết bị báo về (GPS/Wi-Fi của máy Android hoặc trình duyệt)
            ex("UPDATE devices SET gps_lat=?, gps_lng=?, gps_acc=?, gps_src=?, gps_at=? WHERE code=?",
               (glat, glng, gacc, str(g.get("src") or "")[:20], now(), code))
            dev = q("SELECT id, lat, ward_slug FROM devices WHERE code=?", (code,), one=True)
            if dev and dev["lat"] is None and gacc <= 100:
                # Máy mới chưa khai báo vị trí → tự lấy vị trí GPS làm vị trí đặt máy
                ex("UPDATE devices SET lat=?, lng=?, ward_slug=COALESCE(ward_slug, ?) WHERE code=?",
                   (glat, glng, ward_for(glat, glng), code))
    return jsonify(ok=True, server_time=now(), config_version=get_setting("config_version", 0), data_version=data_version())


DATA_ACTIONS = ("poi.", "revision.", "ads.", "category.", "ward.", "transit.", "module.", "settings.", "device.", "import.commit")


def data_version():
    """Mốc thay đổi dữ liệu công khai gần nhất — kiosk/ứng dụng Android dùng để tự cập nhật."""
    cond = " OR ".join("action LIKE ?" for _ in DATA_ACTIONS)
    r = q(f"SELECT MAX(at) AS v FROM audit WHERE {cond}", tuple(a + ("%" if a.endswith(".") else "") for a in DATA_ACTIONS), one=True)
    r2 = q("SELECT MAX(COALESCE(published_at, updated_at, 0)) AS v FROM pois", one=True)
    return max((r and r["v"]) or 0, (r2 and r2["v"]) or 0, get_setting("config_version", 0) or 0)


@app.route("/api/public/version")
def public_version():
    """Kiểm tra nhanh có dữ liệu mới hay không (dùng cho ứng dụng kiosk Android)."""
    return jsonify(data_version=data_version(), config_version=get_setting("config_version", 0), server_time=now(), app_version=VERSION,
                   kiosk_app=get_setting("kiosk_app", {}) or {})


# ======================================================================= auth
@app.route("/api/auth/login", methods=["POST"])
def login():
    d = body()
    username = str(d.get("username") or "").strip().lower()
    key = f"{request.remote_addr}|{username}"
    wait = login_throttled(key)
    if wait:
        return err(f"Đăng nhập sai quá nhiều lần. Thử lại sau {wait} giây.", 429)
    u = q("SELECT * FROM users WHERE lower(username)=?", (username,), one=True)
    if not u or not u["active"] or not check_password(u["password_hash"], d.get("password") or ""):
        login_failed(key)
        return err("Sai tên đăng nhập hoặc mật khẩu", 401)
    login_ok(key)
    ex("UPDATE users SET last_login=? WHERE id=?", (now(), u["id"]))
    g.user = u
    audit("login", "user", u["id"])
    return jsonify(token=issue_token(u), user=public_user(u))


@app.route("/api/auth/me")
@require()
def me():
    if g.user["id"] == 0:
        return jsonify(user={"username": g.user["username"], "role": "CW", "permissions": ["poi.read"]})
    return jsonify(user=public_user(g.user))


@app.route("/api/auth/password", methods=["POST"])
@require()
def change_password():
    d = body()
    if not check_password(g.user["password_hash"], d.get("old_password") or ""):
        return err("Mật khẩu hiện tại không đúng")
    p = password_problem(d.get("new_password"))
    if p:
        return err(p)
    ex("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?", (hash_password(d["new_password"]), g.user["id"]))
    audit("password.change", "user", g.user["id"])
    return jsonify(ok=True)


# ======================================================================= admin: dashboard
@app.route("/api/admin/stats")
@require("stats.read")
def stats():
    t = now()
    day = 86400
    since = t - 30 * day
    by_day = {}
    for r in q("SELECT (at/86400) d, type, COUNT(*) n FROM events WHERE at>=? GROUP BY d, type", (since,)):
        key = datetime.utcfromtimestamp(r["d"] * 86400 + 7 * 3600).strftime("%Y-%m-%d")
        by_day.setdefault(key, {})[r["type"]] = r["n"]
    days = []
    for i in range(29, -1, -1):
        k = datetime.utcfromtimestamp(t - i * day + 7 * 3600).strftime("%Y-%m-%d")
        days.append({"day": k, **by_day.get(k, {})})
    top = [dict(id=r["poi_id"], name=r["name"], n=r["n"]) for r in
           q("""SELECT e.poi_id, p.name, COUNT(*) n FROM events e JOIN pois p ON p.id=e.poi_id
                WHERE e.type='poi_view' AND e.at>=? GROUP BY e.poi_id, p.name ORDER BY n DESC LIMIT 10""", (since,))]
    types = {r["type"]: r["n"] for r in q("SELECT type, COUNT(*) n FROM events WHERE at>=? GROUP BY type", (since,))}
    devs = q("SELECT code,name,last_seen FROM devices WHERE active=1")
    online = sum(1 for d in devs if d["last_seen"] and t - d["last_seen"] < 180)
    return jsonify(
        pois=q("SELECT COUNT(*) n FROM pois WHERE status='published'", one=True)["n"],
        pois_hidden=q("SELECT COUNT(*) n FROM pois WHERE status='hidden'", one=True)["n"],
        wards=q("SELECT COUNT(*) n FROM wards", one=True)["n"],
        pending=q("SELECT COUNT(*) n FROM revisions WHERE status='pending'", one=True)["n"],
        ads_pending=q("SELECT COUNT(*) n FROM ads WHERE status='pending'", one=True)["n"],
        vr=q("SELECT COUNT(*) n FROM pois WHERE status='published' AND vr360 IS NOT NULL AND vr360!='null'", one=True)["n"],
        devices=len(devs), devices_online=online, days=days, top=top, types=types,
        by_category=[dict(r) for r in q("SELECT c.name, c.color, COUNT(p.id) n FROM categories c LEFT JOIN pois p ON p.category=c.id AND p.status='published' GROUP BY c.id ORDER BY n DESC")],
        by_ward=[dict(r) for r in q("SELECT w.short name, COUNT(p.id) n FROM wards w LEFT JOIN pois p ON p.ward_slug=w.slug AND p.status='published' GROUP BY w.slug ORDER BY n DESC LIMIT 12")],
    )


# ======================================================================= admin: POIs
@app.route("/api/admin/pois")
@require("poi.read")
def admin_pois():
    sql = "SELECT p.*, (SELECT COUNT(*) FROM revisions r WHERE r.poi_id=p.id AND r.status='pending') pending FROM pois p WHERE 1=1"
    args = []
    st = request.args.get("status", "")
    if st:
        sql += " AND p.status=?"; args.append(st)
    else:
        sql += " AND p.status!='archived'"
    for k, col in (("ward", "ward_slug"), ("category", "category")):
        if request.args.get(k):
            sql += f" AND p.{col}=?"; args.append(request.args[k])
    if request.args.get("q"):
        sql += " AND (p.name LIKE ? OR p.address LIKE ? OR p.code LIKE ? OR p.tags LIKE ?)"
        like = f"%{request.args['q']}%"; args += [like] * 4
    if request.args.get("vr") == "1":
        sql += " AND p.vr360 IS NOT NULL AND p.vr360!='null'"
    total = q(f"SELECT COUNT(*) n FROM ({sql})", args, one=True)["n"]
    page = max(1, int(request.args.get("page", 1)))
    size = min(200, int(request.args.get("size", 50)))
    sql += " ORDER BY p.updated_at DESC LIMIT ? OFFSET ?"
    rows = [poi_dict(r) for r in q(sql, args + [size, (page - 1) * size])]
    return jsonify(items=rows, total=total, page=page, size=size)


@app.route("/api/admin/pois/<int:pid>")
@require("poi.read")
def admin_poi(pid):
    r = q("SELECT * FROM pois WHERE id=?", (pid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    d = poi_dict(r)
    d["revisions"] = [rev_dict(x) for x in q("SELECT * FROM revisions WHERE poi_id=? ORDER BY id DESC LIMIT 30", (pid,))]
    return jsonify(d)


def rev_dict(r):
    d = row2dict(r, ("data",))
    for k in ("submitted_by", "reviewed_by", "created_by"):
        if d.get(k):
            u = q("SELECT username, full_name FROM users WHERE id=?", (d[k],), one=True)
            d[k + "_name"] = (u["full_name"] or u["username"]) if u else None
    return d


def _propose(action, data, poi_id=None, mode="submit", ward_slug=None):
    """Tạo yêu cầu thay đổi; S1/S0 với mode=publish sẽ duyệt ngay."""
    u = g.user
    if ward_slug and not ward_allowed(u, ward_slug):
        return None, err("Địa điểm thuộc phường ngoài phạm vi được phân công", 403)
    if mode == "publish" and not has_perm(u, "poi.publish"):
        mode = "submit"
    t = now()
    status = {"draft": "draft", "submit": "pending", "publish": "approved"}.get(mode, "pending")
    rid = ex("""INSERT INTO revisions(poi_id,action,data,status,ward_slug,submitted_by,submitted_at,created_by,created_at,updated_at,
                reviewed_by,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
             (poi_id, action, json.dumps(data, ensure_ascii=False), status, ward_slug,
              u["id"] if status != "draft" else None, t if status != "draft" else None, u["id"], t, t,
              u["id"] if status == "approved" else None, t if status == "approved" else None))
    rev = q("SELECT * FROM revisions WHERE id=?", (rid,), one=True)
    pid = poi_id
    if status == "approved":
        pid = apply_revision(rev, u)
    if status == "pending":
        fire_webhook("revision.pending", {"id": rid, "action": action, "poi_id": poi_id})
    audit(f"poi.{action}.{mode}", "poi", pid or f"rev{rid}", {"revision": rid})
    return {"revision_id": rid, "status": status, "poi_id": pid}, None


@app.route("/api/admin/pois", methods=["POST"])
@require("poi.propose")
def admin_poi_create():
    d = body()
    data, errors = clean_poi_data(d.get("data") or d)
    if errors:
        return err("; ".join(errors))
    res, e = _propose("create", data, None, d.get("mode", "submit"), data.get("ward_slug"))
    return e or jsonify(res)


@app.route("/api/admin/pois/<int:pid>", methods=["PUT"])
@require("poi.propose")
def admin_poi_update(pid):
    r = q("SELECT * FROM pois WHERE id=?", (pid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    d = body()
    data, errors = clean_poi_data(d.get("data") or d, partial=True)
    if errors:
        return err("; ".join(errors))
    cur = poi_dict(r)
    changed = {k: v for k, v in data.items() if cur.get(k) != v}
    if not changed:
        return jsonify(ok=True, unchanged=True)
    res, e = _propose("update", changed, pid, d.get("mode", "submit"), r["ward_slug"] or data.get("ward_slug"))
    return e or jsonify(res)


@app.route("/api/admin/pois/<int:pid>", methods=["DELETE"])
@require("poi.propose")
def admin_poi_delete(pid):
    r = q("SELECT * FROM pois WHERE id=?", (pid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    if request.args.get("purge") == "1":
        if not has_perm(g.user, "poi.purge"):
            return err("Chỉ Admin S0 được xoá vĩnh viễn", 403)
        ex("DELETE FROM pois WHERE id=?", (pid,))
        audit("poi.purge", "poi", pid, {"name": r["name"]})
        return jsonify(ok=True, purged=True)
    mode = "publish" if has_perm(g.user, "poi.publish") else "submit"
    res, e = _propose("delete", {"reason": body().get("reason", "")}, pid, mode, r["ward_slug"])
    return e or jsonify(res)


@app.route("/api/admin/pois/<int:pid>/status", methods=["POST"])
@require("poi.publish")
def admin_poi_status(pid):
    st = body().get("status")
    if st not in ("published", "hidden", "archived"):
        return err("Trạng thái không hợp lệ")
    ex("UPDATE pois SET status=?, updated_at=? WHERE id=?", (st, now(), pid))
    audit("poi.status", "poi", pid, {"status": st})
    fire_webhook("poi.status", {"id": pid, "status": st})
    return jsonify(ok=True)


# ======================================================================= admin: revisions / approval
@app.route("/api/admin/revisions")
@require("poi.read")
def admin_revisions():
    sql = "SELECT * FROM revisions WHERE 1=1"
    args = []
    st = request.args.get("status")
    if st:
        sql += " AND status=?"; args.append(st)
    if request.args.get("mine") == "1" or not has_perm(g.user, "poi.approve"):
        sql += " AND created_by=?"; args.append(g.user["id"])
    if request.args.get("batch"):
        sql += " AND batch_id=?"; args.append(request.args["batch"])
    sql += " ORDER BY COALESCE(submitted_at, created_at) DESC LIMIT 500"
    items = []
    for r in q(sql, args):
        d = rev_dict(r)
        if d.get("poi_id"):
            p = q("SELECT name, code FROM pois WHERE id=?", (d["poi_id"],), one=True)
            d["poi_name"] = p["name"] if p else None
            d["poi_code"] = p["code"] if p else None
        items.append(d)
    return jsonify(items=items)


@app.route("/api/admin/revisions/<int:rid>")
@require("poi.read")
def admin_revision(rid):
    r = q("SELECT * FROM revisions WHERE id=?", (rid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    d = rev_dict(r)
    if r["poi_id"]:
        p = q("SELECT * FROM pois WHERE id=?", (r["poi_id"],), one=True)
        d["current"] = poi_dict(p) if p else None
    return jsonify(d)


@app.route("/api/admin/revisions/<int:rid>", methods=["PUT"])
@require("poi.propose")
def admin_revision_edit(rid):
    r = q("SELECT * FROM revisions WHERE id=?", (rid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    if r["status"] not in ("draft", "rejected", "pending"):
        return err("Yêu cầu đã xử lý, không thể sửa")
    if r["created_by"] != g.user["id"] and not has_perm(g.user, "poi.approve"):
        return err("Chỉ người tạo được sửa bản nháp", 403)
    d = body()
    data, errors = clean_poi_data(d.get("data") or {}, partial=r["action"] != "create")
    if errors:
        return err("; ".join(errors))
    new_status = "pending" if d.get("submit") else ("draft" if r["status"] == "rejected" else r["status"])
    ex("UPDATE revisions SET data=?, status=?, updated_at=?, submitted_at=COALESCE(?,submitted_at), submitted_by=COALESCE(?,submitted_by) WHERE id=?",
       (json.dumps(data, ensure_ascii=False), new_status, now(), now() if new_status == "pending" else None,
        g.user["id"] if new_status == "pending" else None, rid))
    audit("revision.edit", "revision", rid)
    return jsonify(ok=True, status=new_status)


@app.route("/api/admin/revisions/<int:rid>/<action>", methods=["POST"])
@require("poi.propose")
def admin_revision_action(rid, action):
    r = q("SELECT * FROM revisions WHERE id=?", (rid,), one=True)
    if not r:
        return err("Không tìm thấy", 404)
    note = str(body().get("note") or "")[:1000]
    t = now()
    if action == "submit":
        if r["created_by"] != g.user["id"] and not has_perm(g.user, "poi.approve"):
            return err("Không có quyền", 403)
        if r["status"] not in ("draft", "rejected"):
            return err("Chỉ gửi được bản nháp hoặc bản bị từ chối")
        ex("UPDATE revisions SET status='pending', submitted_by=?, submitted_at=? WHERE id=?", (g.user["id"], t, rid))
    elif action == "cancel":
        if r["created_by"] != g.user["id"] and not has_perm(g.user, "poi.approve"):
            return err("Không có quyền", 403)
        if r["status"] in ("approved",):
            return err("Đã duyệt, không thể huỷ")
        ex("UPDATE revisions SET status='cancelled', updated_at=? WHERE id=?", (t, rid))
    elif action in ("approve", "reject"):
        if not has_perm(g.user, "poi.approve"):
            return err("Chỉ Admin S1/S0 được phê duyệt", 403)
        if r["status"] != "pending":
            return err("Yêu cầu không ở trạng thái chờ duyệt")
        if not ward_allowed(g.user, r["ward_slug"]):
            return err("Ngoài phạm vi phường được phân công", 403)
        if action == "reject":
            if not note:
                return err("Vui lòng nhập lý do từ chối")
            ex("UPDATE revisions SET status='rejected', reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?", (g.user["id"], t, note, rid))
        else:
            try:
                pid = apply_revision(r, g.user)
            except ValueError as e:
                return err(str(e))
            ex("UPDATE revisions SET status='approved', reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?", (g.user["id"], t, note, rid))
            fire_webhook("revision.approved", {"id": rid, "poi_id": pid})
    else:
        return err("Thao tác không hợp lệ", 404)
    audit(f"revision.{action}", "revision", rid, {"note": note} if note else None)
    return jsonify(ok=True)


@app.route("/api/admin/revisions/bulk", methods=["POST"])
@require("poi.approve")
def admin_revision_bulk():
    d = body()
    ids = [int(i) for i in d.get("ids", [])][:500]
    action = d.get("action")
    note = str(d.get("note") or "")
    if action == "reject" and not note:
        return err("Vui lòng nhập lý do từ chối")
    ok, fail = 0, []
    t = now()
    for rid in ids:
        r = q("SELECT * FROM revisions WHERE id=? AND status='pending'", (rid,), one=True)
        if not r or not ward_allowed(g.user, r["ward_slug"]):
            fail.append(rid); continue
        try:
            if action == "approve":
                apply_revision(r, g.user)
                ex("UPDATE revisions SET status='approved', reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?", (g.user["id"], t, note, rid))
            elif action == "reject":
                ex("UPDATE revisions SET status='rejected', reviewed_by=?, reviewed_at=?, review_note=? WHERE id=?", (g.user["id"], t, note, rid))
            ok += 1
        except Exception:
            fail.append(rid)
    audit(f"revision.bulk_{action}", "revision", ",".join(map(str, ids[:20])), {"ok": ok, "fail": fail})
    return jsonify(ok=ok, failed=fail)


# ======================================================================= admin: uploads & import
@app.route("/api/admin/upload", methods=["POST"])
@require("media.upload")
def admin_upload():
    f = request.files.get("file")
    if not f:
        return err("Thiếu tệp")
    kind = request.form.get("kind", "image")
    try:
        res = save_upload(f.read(), f.filename, kind=kind)
    except ValueError as e:
        return err(str(e))
    except Exception:
        return err("Không đọc được tệp ảnh")
    audit("media.upload", "media", res["url"])
    return jsonify(res)


@app.route("/api/admin/import/template")
def import_template():
    data = importer.build_template()
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=Xanh24_Mau_Nhap_Dia_Diem.xlsx"})


@app.route("/api/admin/import/preview", methods=["POST"])
@require("import.run")
def import_preview():
    f = request.files.get("file")
    if not f or not f.filename.lower().endswith((".xlsx", ".xlsm")):
        return err("Vui lòng chọn tệp Excel .xlsx theo biểu mẫu")
    z = request.files.get("zip")
    try:
        bid, rows = importer.parse_workbook(f.read(), z.read() if z else None)
    except ValueError as e:
        return err(str(e))
    except Exception as e:  # noqa
        return err("Không đọc được tệp Excel: " + str(e)[:200])
    for r in rows:
        if r["data"].get("ward_slug") and not ward_allowed(g.user, r["data"]["ward_slug"]):
            r["errors"].append("Phường ngoài phạm vi tài khoản được phân công")
    valid = sum(1 for r in rows if not r["errors"])
    ex("INSERT INTO import_batches(id,filename,created_by,created_at,total,valid,rows,status) VALUES(?,?,?,?,?,?,?,'preview')",
       (bid, f.filename, g.user["id"], now(), len(rows), valid, json.dumps(rows, ensure_ascii=False)))
    audit("import.preview", "import", bid, {"file": f.filename, "rows": len(rows), "valid": valid})
    return jsonify(batch_id=bid, total=len(rows), valid=valid, rows=rows)


@app.route("/api/admin/import/<bid>/commit", methods=["POST"])
@require("import.run")
def import_commit(bid):
    b = q("SELECT * FROM import_batches WHERE id=?", (bid,), one=True)
    if not b or b["created_by"] != g.user["id"] and not has_perm(g.user, "poi.approve"):
        return err("Không tìm thấy lô nhập", 404)
    if b["status"] != "preview":
        return err("Lô này đã được xử lý")
    d = body()
    mode = d.get("mode", "submit")
    include = set(d.get("rows") or [])
    rows = json.loads(b["rows"])
    done, skipped = 0, 0
    for r in rows:
        if r["errors"] or (include and r["row"] not in include):
            skipped += 1
            continue
        data = {k: v for k, v in r["data"].items() if k in POI_FIELDS and v not in (None, "")}
        if r["data"].get("images") == []:
            data.pop("images", None)
        res, e = _propose(r["action"], data, r.get("poi_id"), mode, data.get("ward_slug"))
        if e:
            skipped += 1
            continue
        ex("UPDATE revisions SET batch_id=? WHERE id=?", (bid, res["revision_id"]))
        done += 1
    ex("UPDATE import_batches SET status=? WHERE id=?", (f"committed:{mode}", bid))
    audit("import.commit", "import", bid, {"mode": mode, "done": done, "skipped": skipped})
    return jsonify(ok=True, done=done, skipped=skipped, mode=mode)


@app.route("/api/admin/import/batches")
@require("import.run")
def import_batches():
    sql = "SELECT id,filename,created_by,created_at,total,valid,status FROM import_batches"
    args = []
    if not has_perm(g.user, "poi.approve"):
        sql += " WHERE created_by=?"; args.append(g.user["id"])
    sql += " ORDER BY created_at DESC LIMIT 50"
    return jsonify(items=[dict(r) for r in q(sql, args)])


# ======================================================================= admin: generic CRUD helpers
def _crud_list(table, order="id DESC", json_fields=()):
    return jsonify(items=[row2dict(r, json_fields) for r in q(f"SELECT * FROM {table} ORDER BY {order}")])


def _upsert(table, allowed, d, key="id", key_val=None, json_fields=(), extra=None):
    data = {k: (json.dumps(d[k], ensure_ascii=False) if k in json_fields else d[k]) for k in allowed if k in d}
    if extra:
        data.update(extra)
    if key_val is None:
        cols = list(data)
        return ex(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [data[c] for c in cols])
    if data:
        ex(f"UPDATE {table} SET {','.join(k + '=?' for k in data)} WHERE {key}=?", [*data.values(), key_val])
    return key_val


# ---- ads
AD_FIELDS = ["title", "media_type", "media_url", "html", "duration_sec", "start_at", "end_at", "priority",
             "target_devices", "target_wards", "link_poi"]


@app.route("/api/admin/ads")
@require("poi.read")
def admin_ads():
    return _crud_list("ads", "priority DESC, id DESC", ("target_devices", "target_wards"))


@app.route("/api/admin/ads", methods=["POST"])
@app.route("/api/admin/ads/<int:aid>", methods=["PUT"])
@require("ads.propose")
def admin_ad_save(aid=None):
    d = body()
    if not str(d.get("title") or "").strip():
        return err("Thiếu tiêu đề")
    publish = has_perm(g.user, "ads.publish") and d.get("publish")
    status = "published" if publish else "pending"
    aid = _upsert("ads", AD_FIELDS, d, key_val=aid, json_fields=("target_devices", "target_wards"),
                  extra={"status": status, "updated_at": now(), **({"created_by": g.user["id"], "created_at": now()} if aid is None else {}),
                         **({"approved_by": g.user["id"]} if publish else {})})
    audit("ads.save", "ads", aid, {"status": status})
    return jsonify(ok=True, id=aid, status=status)


@app.route("/api/admin/ads/<int:aid>/<action>", methods=["POST"])
@require("ads.publish")
def admin_ad_action(aid, action):
    st = {"approve": "published", "reject": "rejected", "archive": "archived"}.get(action)
    if not st:
        return err("Thao tác không hợp lệ", 404)
    ex("UPDATE ads SET status=?, approved_by=?, updated_at=? WHERE id=?", (st, g.user["id"], now(), aid))
    audit(f"ads.{action}", "ads", aid)
    return jsonify(ok=True)


@app.route("/api/admin/ads/<int:aid>", methods=["DELETE"])
@require("ads.publish")
def admin_ad_delete(aid):
    ex("DELETE FROM ads WHERE id=?", (aid,))
    audit("ads.delete", "ads", aid)
    return jsonify(ok=True)


# ---- devices
DEV_FIELDS = ["code", "name", "ward_slug", "address", "lat", "lng", "bearing", "orientation", "idle_timeout", "config", "notes", "active", "location_mode"]


@app.route("/api/admin/devices")
@require("poi.read")
def admin_devices():
    items = [row2dict(r, ("config",)) for r in q("SELECT * FROM devices ORDER BY code")]
    t = now()
    for d in items:
        d["online"] = bool(d["last_seen"] and t - d["last_seen"] < 180)
    return jsonify(items=items)


@app.route("/api/admin/devices", methods=["POST"])
@app.route("/api/admin/devices/<int:did>", methods=["PUT"])
@require("devices.manage")
def admin_device_save(did=None):
    d = body()
    if did is None:
        if not re.match(r"^[A-Za-z0-9_-]{2,40}$", str(d.get("code") or "")):
            return err("Mã thiết bị 2–40 ký tự: chữ, số, - hoặc _")
        if q("SELECT 1 FROM devices WHERE code=?", (d["code"],), one=True):
            return err("Mã thiết bị đã tồn tại")
        if not d.get("name"):
            return err("Thiếu tên thiết bị")
    try:
        did = _upsert("devices", DEV_FIELDS, d, key_val=did, json_fields=("config",),
                      extra={"created_at": now()} if did is None else None)
    except Exception as e:  # noqa
        return err("Không lưu được: " + str(e))
    set_setting("config_version", now())
    audit("device.save", "device", did)
    return jsonify(ok=True, id=did)


@app.route("/api/admin/devices/<int:did>", methods=["DELETE"])
@require("devices.manage")
def admin_device_delete(did):
    ex("DELETE FROM devices WHERE id=?", (did,))
    audit("device.delete", "device", did)
    return jsonify(ok=True)


# ---- wards
@app.route("/api/admin/wards")
@require("poi.read")
def admin_wards():
    items = []
    for r in q("SELECT w.*, (SELECT COUNT(*) FROM pois p WHERE p.ward_slug=w.slug AND p.status='published') n FROM wards w ORDER BY short"):
        d = row2dict(r, ("hq", "info"))
        if request.args.get("geometry") != "1":
            d.pop("geometry", None)
        else:
            d["geometry"] = json.loads(d["geometry"]) if d.get("geometry") else None
        items.append(d)
    return jsonify(items=items)


@app.route("/api/admin/wards/<slug>", methods=["PUT"])
@require("wards.edit_info")
def admin_ward_save(slug):
    w = q("SELECT * FROM wards WHERE slug=?", (slug,), one=True)
    if not w:
        return err("Không tìm thấy phường", 404)
    d = body()
    upd = {}
    for k in ("name", "short", "published"):
        if k in d:
            upd[k] = d[k]
    if "info" in d:
        upd["info"] = json.dumps(d["info"], ensure_ascii=False)
    if "hq" in d:
        upd["hq"] = json.dumps(d["hq"])
    if "geometry" in d:
        if not has_perm(g.user, "wards.edit_geometry"):
            return err("Chỉ Admin S0 được sửa ranh giới", 403)
        geom = d["geometry"]
        if geom and geom.get("type") == "Feature":
            geom = geom["geometry"]
        if geom and geom.get("type") == "FeatureCollection":
            geom = geom["features"][0]["geometry"]
        problem = validate_geometry(geom)
        if problem:
            return err(problem)
        upd["geometry"] = json.dumps(geom)
        upd["area_km2"] = round(area_km2(geom), 2)
        upd["source"] = str(d.get("source") or "Cập nhật bởi quản trị")[:300]
    if not upd:
        return err("Không có thay đổi")
    upd["updated_at"] = now()
    upd["updated_by"] = g.user["username"]
    ex(f"UPDATE wards SET {','.join(k + '=?' for k in upd)} WHERE slug=?", [*upd.values(), slug])
    if "geometry" in upd and d.get("reassign"):
        # gán lại phường cho các địa điểm theo ranh giới mới
        g._wg = None
        for p in q("SELECT id,lat,lng FROM pois"):
            ex("UPDATE pois SET ward_slug=? WHERE id=?", (ward_for(p["lat"], p["lng"]), p["id"]))
    audit("ward.update", "ward", slug, {"fields": list(upd)})
    fire_webhook("ward.updated", {"slug": slug})
    return jsonify(ok=True)


@app.route("/api/admin/wards", methods=["POST"])
@require("wards.edit_geometry")
def admin_ward_create():
    d = body()
    slug = re.sub(r"[^a-z0-9-]", "", str(d.get("slug") or "").lower())
    if not slug or not d.get("name"):
        return err("Thiếu slug hoặc tên")
    if q("SELECT 1 FROM wards WHERE slug=?", (slug,), one=True):
        return err("Slug đã tồn tại")
    geom = d.get("geometry")
    if geom:
        problem = validate_geometry(geom)
        if problem:
            return err(problem)
    ex("INSERT INTO wards(slug,name,short,type,area_km2,geometry,source,published,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,1,?,?)",
       (slug, d["name"], d.get("short") or d["name"], d.get("type", "phuong"), round(area_km2(geom), 2) if geom else None,
        json.dumps(geom) if geom else None, d.get("source", "Quản trị tạo mới"), now(), g.user["username"]))
    audit("ward.create", "ward", slug)
    return jsonify(ok=True, slug=slug)


@app.route("/api/admin/wards/export.geojson")
@require("poi.read")
def admin_wards_export():
    feats = []
    for r in q("SELECT * FROM wards WHERE geometry IS NOT NULL"):
        feats.append({"type": "Feature", "properties": {"slug": r["slug"], "name": r["name"], "area_km2": r["area_km2"], "source": r["source"]},
                      "geometry": json.loads(r["geometry"])})
    return Response(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
                    mimetype="application/geo+json", headers={"Content-Disposition": "attachment; filename=xanh24_ranh_gioi.geojson"})


# ---- categories
@app.route("/api/admin/categories")
@require("poi.read")
def admin_categories():
    return _crud_list("categories", "sort")


@app.route("/api/admin/categories", methods=["POST"])
@app.route("/api/admin/categories/<cid>", methods=["PUT"])
@require("poi.approve")
def admin_category_save(cid=None):
    d = body()
    if cid is None:
        cid_new = re.sub(r"[^a-z0-9-]", "", str(d.get("id") or "").lower())
        if not cid_new or not d.get("name"):
            return err("Thiếu mã hoặc tên danh mục")
        if q("SELECT 1 FROM categories WHERE id=?", (cid_new,), one=True):
            return err("Mã danh mục đã tồn tại")
        ex("INSERT INTO categories(id,name,name_en,icon,color,sort,active) VALUES(?,?,?,?,?,?,1)",
           (cid_new, d["name"], d.get("name_en", ""), d.get("icon", "pin"), d.get("color", "#2A62B8"), int(d.get("sort", 99))))
        cid = cid_new
    else:
        _upsert("categories", ["name", "name_en", "icon", "color", "sort", "active"], d, key="id", key_val=cid)
    audit("category.save", "category", cid)
    return jsonify(ok=True, id=cid)


# ---- transit
@app.route("/api/admin/transit")
@require("poi.read")
def admin_transit():
    return public_transit()


@app.route("/api/admin/transit/stops", methods=["POST"])
@app.route("/api/admin/transit/stops/<int:sid>", methods=["PUT"])
@require("transit.manage")
def admin_stop_save(sid=None):
    d = body()
    sid = _upsert("transit_stops", ["kind", "name", "lat", "lng", "lines", "note", "verified"], d, key_val=sid, json_fields=("lines",))
    audit("transit.stop", "stop", sid)
    return jsonify(ok=True, id=sid)


@app.route("/api/admin/transit/stops/<int:sid>", methods=["DELETE"])
@require("transit.manage")
def admin_stop_delete(sid):
    ex("DELETE FROM transit_stops WHERE id=?", (sid,))
    return jsonify(ok=True)


@app.route("/api/admin/transit/lines", methods=["POST"])
@app.route("/api/admin/transit/lines/<int:lid>", methods=["PUT"])
@require("transit.manage")
def admin_line_save(lid=None):
    d = body()
    lid = _upsert("transit_lines", ["kind", "code", "name", "color", "operator", "status", "info", "stops", "geometry"], d,
                  key_val=lid, json_fields=("stops", "geometry"), extra={"updated_at": now()})
    audit("transit.line", "line", lid)
    return jsonify(ok=True, id=lid)


@app.route("/api/admin/transit/lines/<int:lid>", methods=["DELETE"])
@require("transit.manage")
def admin_line_delete(lid):
    ex("DELETE FROM transit_lines WHERE id=?", (lid,))
    return jsonify(ok=True)


# ---- users (S0)
@app.route("/api/admin/users")
@require("users.manage")
def admin_users():
    return jsonify(items=[public_user(u) for u in q("SELECT * FROM users ORDER BY role, username")], roles=ROLE_LABEL)


@app.route("/api/admin/users", methods=["POST"])
@app.route("/api/admin/users/<int:uid>", methods=["PUT"])
@require("users.manage")
def admin_user_save(uid=None):
    d = body()
    if d.get("role") and d["role"] not in ROLE_LABEL:
        return err("Vai trò không hợp lệ")
    upd = {k: d[k] for k in ("full_name", "email", "phone", "role", "active") if k in d}
    if "wards" in d:
        upd["wards"] = json.dumps(d["wards"] or [])
    if uid is None:
        un = str(d.get("username") or "").strip().lower()
        if not re.match(r"^[a-z0-9._-]{3,40}$", un):
            return err("Tên đăng nhập 3–40 ký tự (a-z, 0-9, . _ -)")
        if q("SELECT 1 FROM users WHERE lower(username)=?", (un,), one=True):
            return err("Tên đăng nhập đã tồn tại")
        pw = d.get("password") or ""
        p = password_problem(pw)
        if p:
            return err(p)
        upd.update(username=un, password_hash=hash_password(pw), created_at=now(), must_change_password=1)
        upd.setdefault("role", "CW")
        cols = list(upd)
        uid = ex(f"INSERT INTO users({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [upd[c] for c in cols])
        audit("user.create", "user", uid, {"username": un, "role": upd["role"]})
    else:
        if uid == g.user["id"] and (upd.get("role", "S0") != "S0" or upd.get("active") in (0, False)):
            return err("Không thể tự hạ quyền hoặc khoá tài khoản của chính mình")
        if d.get("password"):
            p = password_problem(d["password"])
            if p:
                return err(p)
            upd["password_hash"] = hash_password(d["password"])
            upd["must_change_password"] = 1
        if upd:
            ex(f"UPDATE users SET {','.join(k + '=?' for k in upd)} WHERE id=?", [*upd.values(), uid])
        audit("user.update", "user", uid, {k: v for k, v in upd.items() if k != "password_hash"})
    return jsonify(ok=True, id=uid)


@app.route("/api/admin/users/<int:uid>", methods=["DELETE"])
@require("users.manage")
def admin_user_delete(uid):
    if uid == g.user["id"]:
        return err("Không thể xoá chính mình")
    ex("UPDATE users SET active=0 WHERE id=?", (uid,))
    audit("user.disable", "user", uid)
    return jsonify(ok=True)


# ---- settings (S0)
@app.route("/api/admin/settings")
@require("poi.read")
def admin_settings():
    s = all_settings()
    if not has_perm(g.user, "settings.manage"):
        s = {k: v for k, v in s.items() if k in ("app_name", "idle_timeout", "copyright")}
    return jsonify(s)


@app.route("/api/admin/settings", methods=["PUT"])
@require("settings.manage")
def admin_settings_save():
    d = body()
    allowed = {"app_name", "app_short", "org_name", "copyright", "region_name", "idle_timeout", "idle_warning",
               "default_center", "default_zoom", "tiles", "routing", "ride", "transit", "kiosk", "public_base_url", "languages", "geocode", "kiosk_app"}
    for k, v in d.items():
        if k in allowed:
            if k == "idle_timeout":
                v = max(10, min(600, int(v)))
            set_setting(k, v)
    set_setting("config_version", now())
    audit("settings.update", "settings", ",".join(k for k in d if k in allowed))
    return jsonify(ok=True)


# ---- modules (S0)
MOD_FIELDS = ["name", "description", "kind", "entry_url", "icon", "color", "placement", "enabled", "config", "sort", "version"]


@app.route("/api/admin/modules")
@require("poi.read")
def admin_modules():
    return _crud_list("modules", "sort", ("config",))


@app.route("/api/admin/modules", methods=["POST"])
@app.route("/api/admin/modules/<key>", methods=["PUT"])
@require("modules.manage")
def admin_module_save(key=None):
    d = body()
    if key is None:
        key = re.sub(r"[^a-z0-9_-]", "", str(d.get("key") or "").lower())
        if not key or not d.get("name"):
            return err("Thiếu mã hoặc tên module")
        if q("SELECT 1 FROM modules WHERE key=?", (key,), one=True):
            return err("Mã module đã tồn tại")
        ex("INSERT INTO modules(key,name,updated_at) VALUES(?,?,?)", (key, d["name"], now()))
    if d.get("kind") == "iframe" and d.get("entry_url") and not (d["entry_url"].startswith("/") or d["entry_url"].startswith("https://")):
        return err("URL module phải bắt đầu bằng / hoặc https://")
    _upsert("modules", MOD_FIELDS, d, key="key", key_val=key, json_fields=("config",), extra={"updated_at": now()})
    set_setting("config_version", now())
    audit("module.save", "module", key)
    return jsonify(ok=True, key=key)


@app.route("/api/admin/modules/<key>", methods=["DELETE"])
@require("modules.manage")
def admin_module_delete(key):
    ex("DELETE FROM modules WHERE key=?", (key,))
    audit("module.delete", "module", key)
    return jsonify(ok=True)


# ---- webhooks & API keys (S0)
@app.route("/api/admin/webhooks")
@require("api.manage")
def admin_webhooks():
    items = [row2dict(r, ("events",)) for r in q("SELECT * FROM webhooks ORDER BY id DESC")]
    for i in items:
        i["secret"] = (i["secret"] or "")[:4] + "…"
    keys = [dict(id=r["id"], name=r["name"], prefix=r["prefix"], active=r["active"], created_at=r["created_at"], last_used=r["last_used"])
            for r in q("SELECT * FROM api_keys ORDER BY id DESC")]
    return jsonify(webhooks=items, api_keys=keys)


@app.route("/api/admin/webhooks", methods=["POST"])
@require("api.manage")
def admin_webhook_create():
    d = body()
    if not str(d.get("url") or "").startswith(("https://", "http://")):
        return err("URL webhook không hợp lệ")
    sec = secrets.token_hex(16)
    wid = ex("INSERT INTO webhooks(url,events,secret,active,created_at) VALUES(?,?,?,1,?)",
             (d["url"], json.dumps(d.get("events") or ["*"]), sec, now()))
    audit("webhook.create", "webhook", wid)
    return jsonify(ok=True, id=wid, secret=sec)


@app.route("/api/admin/webhooks/<int:wid>", methods=["DELETE"])
@require("api.manage")
def admin_webhook_delete(wid):
    ex("DELETE FROM webhooks WHERE id=?", (wid,))
    return jsonify(ok=True)


@app.route("/api/admin/apikeys", methods=["POST"])
@require("api.manage")
def admin_apikey_create():
    name = str(body().get("name") or "API key")[:80]
    raw = "x24_" + secrets.token_urlsafe(28)
    kid = ex("INSERT INTO api_keys(name,prefix,key_hash,created_by,created_at) VALUES(?,?,?,?,?)",
             (name, raw[:10], hashlib.sha256(raw.encode()).hexdigest(), g.user["id"], now()))
    audit("apikey.create", "apikey", kid)
    return jsonify(ok=True, id=kid, key=raw)


@app.route("/api/admin/apikeys/<int:kid>", methods=["DELETE"])
@require("api.manage")
def admin_apikey_delete(kid):
    ex("UPDATE api_keys SET active=0 WHERE id=?", (kid,))
    return jsonify(ok=True)


# ---- audit
@app.route("/api/admin/audit")
@require("audit.read")
def admin_audit():
    sql = "SELECT * FROM audit WHERE 1=1"
    args = []
    if request.args.get("q"):
        sql += " AND (username LIKE ? OR action LIKE ? OR entity_id LIKE ?)"
        like = f"%{request.args['q']}%"; args += [like] * 3
    sql += " ORDER BY id DESC LIMIT 300"
    return jsonify(items=[row2dict(r, ("detail",)) for r in q(sql, args)])


@app.route("/api/admin/meta")
@require()
def admin_meta():
    return jsonify(permissions=PERMISSIONS, roles=ROLE_LABEL, version=VERSION)


@app.errorhandler(413)
def too_large(e):
    return err(f"Tệp quá lớn (tối đa {MAX_UPLOAD_MB} MB)", 413)


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return err("Không tìm thấy", 404)
    return send_from_directory(WEB_DIR, "404.html"), 404


# ======================================================================= bootstrap
def create_app():
    # Postgres: khoá tư vấn để nhiều tiến trình khởi động cùng lúc (VD: Vercel) không tạo dữ liệu mẫu trùng
    if IS_PG:
        ex("SELECT pg_advisory_lock(2424)")
    try:
        init_db()
        with app.app_context():
            seed_all(log=lambda m: print(m))
            from modules import load_plugins
            load_plugins(app)
    finally:
        if IS_PG:
            ex("SELECT pg_advisory_unlock(2424)")
    return app


if __name__ == "__main__":
    create_app()
    port = int(os.environ.get("PORT", "8024"))
    print(f"Xanh24 Maps for Life {VERSION} — http://localhost:{port}  (quản trị: /admin)")
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("XANH24_DEBUG")), threaded=True)
