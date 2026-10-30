"""Maps for Life 2.0 (M4L): mobile home, mood tags, discovery, random pick and Fog of War.

Everything here is behind XANH24_M4L_ENABLED (off by default). While it is off,
no table is created and every /m4l and /api/m4l route answers 404.
Identity reuses the CMS token; moods and areas are managed by S0, POI links and
mystery pins by S0/CONTENT within their wards. Location is never tracked in the
background: the client sends samples only while the user has exploration switched on.
"""
import functools
import hashlib
import json
import os

import jwt
from flask import Blueprint, abort, g, jsonify, request, send_from_directory

import m4l_commerce as commerce
import m4l_exploration as geo
import m4l_migrations
import m4l_service as svc
from auth import secret
from cms import authenticate, role, wards
from db import BASE_DIR, ex, get_db, now, q

m4l = Blueprint("m4l", __name__)
WEB_DIR = os.path.join(BASE_DIR, "web", "m4l")
USER_PAGES = {"", "discover", "world", "vouchers"}
STAFF_PAGES = {"partner": "partner.html", "station": "station.html"}
_state = {"ready": False, "error": ""}


def enabled():
    return os.environ.get("XANH24_M4L_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def init_m4l(log=print):
    """Apply pending M4L migrations (with a SQLite backup first). Returns True when the module can serve."""
    if not enabled():
        _state.update(ready=False, error="")
        return False
    try:
        m4l_migrations.migrate(log=log)
        for area in q("SELECT * FROM m4l_areas WHERE status='active'"):
            geo._aggregates(area)  # warm the per-version totals/blocks so the first map view is fast
        _state.update(ready=True, error="")
    except Exception as exc:  # the rest of the app must keep running
        _state.update(ready=False, error=str(exc))
        log(f"  ! M4L chưa sẵn sàng: {exc}")
    return _state["ready"]


def fail(message, status=400, code="INVALID_PARAMETER"):
    return jsonify(error=message, code=code), status


@m4l.before_request
def gate():
    if not enabled():
        abort(404)
    if not _state["ready"]:
        if request.path.startswith("/api/"):
            return fail("Tính năng M4L tạm thời chưa sẵn sàng", 503, "M4L_UNAVAILABLE")
        return "Tính năng M4L tạm thời chưa sẵn sàng", 503


@m4l.errorhandler(svc.ServiceError)
def service_error(exc):
    return fail(exc.message, exc.status, exc.code)


def optional_account():
    """(account dict | None, token_was_invalid). Never fails the request."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, False
    try:
        claims = jwt.decode(header[7:], secret(), algorithms=["HS256"])
        if not claims.get("cms"):
            return None, False
        row = q("SELECT * FROM cms_accounts WHERE id=? AND active=1", (int(claims["sub"]),), one=True)
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None, True
    return (dict(row), False) if row else (None, True)


def user_account():
    """Logged-in USER account or a ServiceError(401/403)."""
    account, _ = optional_account()
    if not account:
        raise svc.ServiceError("Cần đăng nhập để dùng tính năng này", "UNAUTHENTICATED", 401)
    if account["role"] != "USER":
        raise svc.ServiceError("Tính năng dành cho tài khoản người dùng", "FORBIDDEN", 403)
    return account


def actor():
    return g.cms_user["username"]


def record(action, entity, entity_id, detail):
    user = g.cms_user
    detail = {**detail, "account_table": "users" if user["role"] == "S0" else "cms_accounts"}
    ex("INSERT INTO audit(user_id,username,action,entity,entity_id,detail,ip,at) VALUES(?,?,?,?,?,?,?,?)",
       (user["id"], user["username"], action, entity, str(entity_id),
        json.dumps(detail, ensure_ascii=False), request.remote_addr, now()))


# ---------------------------------------------------------------- pages
@m4l.route("/m4l")
@m4l.route("/m4l/<path:name>")
def pages(name=""):
    name = name.rstrip("/")
    if name in USER_PAGES or (name.startswith("k/") and name.count("/") == 1):
        response = send_from_directory(WEB_DIR, "index.html")
    elif name in STAFF_PAGES or (name.startswith("v/") and name.count("/") == 1):
        response = send_from_directory(WEB_DIR, STAFF_PAGES.get(name, "partner.html"))
        response.headers["X-Robots-Tag"] = "noindex"
    elif name == "admin":
        response = send_from_directory(WEB_DIR, "admin.html")
        response.headers["X-Robots-Tag"] = "noindex"
    elif name.endswith((".js", ".css")) and "/" not in name:
        return send_from_directory(WEB_DIR, name, max_age=0)
    else:
        abort(404)
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------------------------------------------------------------- public API
@m4l.route("/api/m4l/home")
def home():
    account, expired = optional_account()
    user = None
    if account and account["role"] == "USER":
        display = (account["full_name"] or account["username"]).strip()
        user = {"display_name": display, "first_name": display.split()[-1] if display else ""}
    area = geo.get_area()
    import m4l_demo
    features = {"discovery": True, "random": True, "exploration": bool(area), "vouchers": True, "demo": m4l_demo.enabled()}
    progress = geo.progress(account["id"], area) if user and area else None
    vouchers = None
    if user:
        mine = [v for v in commerce.wallet(account["id"]) if v["status"] == "issued"]
        vouchers = {"active": len(mine), "next": mine[0] if mine else None}
    return jsonify(user=user, session_expired=expired, moods=svc.list_moods(), features=features,
                   area={"slug": area["slug"], "name": area["name"]} if area else None,
                   progress=progress, vouchers=vouchers, server_time=now())


@m4l.route("/api/m4l/moods")
def moods():
    items = svc.list_moods()
    return jsonify(items=items, total=len(items))


def viewer():
    """Who is looking, for de-duplicating impressions. Guests are keyed by a daily hash of their IP, never stored raw."""
    account = _user_or_none()
    if account:
        return {"account_id": account["id"], "key": f"a{account['id']}"}
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    return {"account_id": None, "key": "g" + hashlib.sha256(f"{ip}|{now() // 86400}".encode()).hexdigest()[:16]}


@m4l.route("/api/m4l/discovery")
def discovery():
    params = svc.parse_discovery(request.args)
    result = svc.discover(params)
    commerce.attach_offers(result["items"])
    result["sponsored"] = None
    if result["mood"] and params["cursor"] == 0 and not params["q"] and not params["category"]:
        mood = q("SELECT * FROM m4l_moods WHERE slug=?", (result["mood"]["slug"],), one=True)
        item = commerce.sponsor_for(mood, params["location"], viewer())
        if item:
            commerce.attach_offers([item])
            result["sponsored"] = item  # separate labelled slot; the organic list and its order are untouched
    return jsonify(result)


@m4l.route("/api/m4l/discovery/random", methods=["POST"])
def random_pick():
    account = user_account()
    return jsonify(svc.random_pick(account["id"], request.get_json(silent=True) or {}))


# ---------------------------------------------------------------- offers, vouchers, kiosk check-in, events
@m4l.route("/api/m4l/offers")
def offers():
    """Live partner offers for the home page, nearest first when a (rounded) location is given."""
    params = svc.parse_discovery(request.args)
    location = params["location"]
    rows = [r for kind in ("mood_sponsor", "vip_spin") for r in commerce.live_campaigns(kind) if commerce.within(r, location)]
    by_poi = commerce.offers_for_pois(sorted({r["poi_id"] for r in rows}))
    items = []
    for poi_id, offer in by_poi.items():
        poi = q("SELECT id, name, address, lat, lng, ward_slug FROM pois WHERE id=?", (poi_id,), one=True)
        distance = svc.haversine_m(location[0], location[1], poi["lat"], poi["lng"]) if location else None
        items.append(offer | {"poi_id": poi_id, "poi_name": poi["name"], "address": poi["address"],
                              "distance_m": round(distance) if distance is not None else None})
    items.sort(key=lambda o: (o["distance_m"] if o["distance_m"] is not None else 0, -o["remaining"], o["campaign_id"]))
    items = items[:params["limit"]]
    who = viewer()
    with svc.transaction() as conn:
        for o in items:
            commerce.impression(conn, who, o["campaign_id"], o["poi_id"], "home")
    return jsonify(items=items, total=len(items))


@m4l.route("/api/m4l/vouchers")
def vouchers_mine():
    account = user_account()
    return jsonify(items=commerce.wallet(account["id"]), server_time=now())


@m4l.route("/api/m4l/vouchers/<int:voucher_id>")
def voucher_mine(voucher_id):
    account = user_account()
    return jsonify(commerce.voucher_by_id(account["id"], voucher_id) | {"server_time": now()})


@m4l.route("/api/m4l/vouchers/claim", methods=["POST"])
def voucher_claim():
    account = user_account()
    d = request.get_json(silent=True) or {}
    campaign_id = svc._int(d.get("campaign_id"), "campaign_id", 1, 2 ** 31)
    if not campaign_id:
        raise svc.ServiceError("Thiếu campaign_id")
    session_id = svc._int(d.get("kiosk_session_id"), "kiosk_session_id", 1, 2 ** 31)
    result = commerce.claim(account["id"], campaign_id, str(d.get("source") or "discovery"), d.get("idempotency_key"), session_id)
    voucher = commerce.voucher_by_id(account["id"], result["voucher_id"])
    return jsonify(voucher=voucher, replayed=result["replayed"], server_time=now()), 200 if result["replayed"] else 201


@m4l.route("/api/m4l/events", methods=["POST"])
def client_events():
    account = _user_or_none()
    return jsonify(commerce.client_event(account["id"] if account else None, request.get_json(silent=True) or {}))


@m4l.route("/api/m4l/kiosk/ticket", methods=["POST"])
def kiosk_ticket():
    """Called by the kiosk screen with its own key (never a user token)."""
    d = request.get_json(silent=True) or {}
    out = commerce.kiosk_ticket(d.get("device"), request.headers.get("X-Kiosk-Key"), d.get("current"))
    return jsonify(out | {"path": f"/m4l/k/{out['token']}", "server_time": now()})


@m4l.route("/api/m4l/kiosk/checkin", methods=["POST"])
def kiosk_checkin():
    account = user_account()
    return jsonify(commerce.kiosk_checkin(account["id"], (request.get_json(silent=True) or {}).get("ticket")))


# ---------------------------------------------------------------- exploration
def _area_arg():
    slug = str(request.args.get("area") or (request.get_json(silent=True) or {}).get("area") or "").strip()
    area = geo.get_area(slug or None)
    if not area:
        raise svc.ServiceError("Chưa có khu vực khám phá nào được bật", "AREA_NOT_FOUND", 404)
    return area


def _user_or_none():
    account, _ = optional_account()
    return account if account and account["role"] == "USER" else None


def _bbox_arg():
    raw = request.args.get("bbox")
    return geo.parse_bbox(raw) if raw else None


@m4l.route("/api/m4l/exploration")
def exploration():
    """Viewport-limited grid: ?bbox=minLng,minLat,maxLng,maxLat&level=auto|cells|blocks. Never the whole city cell list."""
    area = _area_arg()
    mine = _user_or_none()
    bbox = _bbox_arg()
    cfg = svc.config()
    rules = {"max_accuracy_m": cfg["unlock_max_accuracy_m"], "min_samples": cfg["unlock_min_samples"]}
    data = geo.view(area, bbox, request.args.get("level", "auto"), mine["id"] if mine else None)
    return jsonify(area=geo.area_public(area), rules=rules, max_view_cells=geo.MAX_VIEW_CELLS, **data,
                   progress=geo.progress(mine["id"], area) if mine else None,
                   pins=geo.pins_for(area, mine["id"] if mine else None, bbox))


@m4l.route("/api/m4l/exploration/progress")
def exploration_progress():
    account = user_account()
    return jsonify(geo.progress(account["id"], _area_arg(), breakdown=request.args.get("breakdown") == "unit"))


@m4l.route("/api/m4l/areas")
def areas_public():
    items = [{k: a[k] for k in ("slug", "name", "kind", "cell_size_m", "grid_version", "classification_version", "eligible_cell_count")}
             for a in geo.list_areas() if a["status"] == "active"]
    return jsonify(items=items, primary=(geo.get_area() or {"slug": None})["slug"])


@m4l.route("/api/m4l/areas/<slug>/boundary")
def area_boundary(slug):
    area = geo.get_area(slug)
    response = jsonify(area={"slug": area["slug"], "name": area["name"], "kind": area["kind"]}, **geo.boundary(area))
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@m4l.route("/api/m4l/exploration/unlock", methods=["POST"])
def exploration_unlock():
    account = user_account()
    area = _area_arg()
    return jsonify(geo.unlock(account["id"], area, (request.get_json(silent=True) or {}).get("samples")))


@m4l.route("/api/m4l/exploration/me", methods=["DELETE"])
def exploration_forget():
    account = user_account()
    geo.forget_account(account["id"])
    return jsonify(ok=True)


@m4l.route("/api/m4l/mystery-pins")
def mystery_pins():
    area = _area_arg()
    mine = _user_or_none()
    items = geo.pins_for(area, mine["id"] if mine else None, _bbox_arg())
    return jsonify(items=items, total=len(items))


# ---------------------------------------------------------------- admin API
def staff(*roles):
    """CMS login (legacy S0 included) restricted to the given roles."""
    def deco(fn):
        @authenticate
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if not role(*roles):
                return fail("Bạn không có quyền thực hiện thao tác này", 403, "FORBIDDEN")
            return fn(*args, **kwargs)
        return wrapped
    return deco


@m4l.route("/api/m4l/admin/moods", methods=["GET"])
@staff("S0", "CONTENT")
def admin_moods():
    items = svc.list_moods(include_inactive=True)
    return jsonify(items=items, total=len(items), can_edit=role("S0"), icons=svc.MOOD_ICONS)


@m4l.route("/api/m4l/admin/moods", methods=["POST"])
@staff("S0")
def admin_mood_create():
    mood = svc.create_mood(request.get_json(silent=True) or {}, actor())
    record("m4l.mood.create", "m4l_mood", mood["id"], {"after": mood})
    return jsonify(mood), 201


@m4l.route("/api/m4l/admin/moods/<int:mood_id>", methods=["PUT"])
@staff("S0")
def admin_mood_update(mood_id):
    mood, before = svc.update_mood(mood_id, request.get_json(silent=True) or {})
    record("m4l.mood.update", "m4l_mood", mood_id, {"before": svc.mood_public(before), "after": mood})
    return jsonify(mood)


@m4l.route("/api/m4l/admin/pois", methods=["GET"])
@staff("S0", "CONTENT")
def admin_pois():
    text = svc._text(request.args.get("q"), "từ khóa", 100)
    mood_id = svc._int(request.args.get("mood"), "mood", 1, 2 ** 31)
    return jsonify(svc.admin_pois(wards(), text, mood_id))


@m4l.route("/api/m4l/admin/pois/<int:poi_id>/moods", methods=["PUT"])
@staff("S0", "CONTENT")
def admin_poi_moods(poi_id):
    result, before, after = svc.set_poi_moods(poi_id, request.get_json(silent=True), wards(), actor())
    record("m4l.poi_moods.set", "poi", poi_id, {"before": before, "after": after})
    return jsonify(result)


@m4l.route("/api/m4l/admin/areas", methods=["GET"])
@staff("S0", "CONTENT")
def admin_areas():
    return jsonify(items=geo.list_areas(), can_edit=role("S0"))


@m4l.route("/api/m4l/admin/areas", methods=["POST"])
@staff("S0")
def admin_area_create():
    area = geo.create_area(request.get_json(silent=True) or {}, actor())
    record("m4l.area.create", "m4l_area", area["id"], {"after": area})
    return jsonify(area), 201


@m4l.route("/api/m4l/admin/areas/<int:area_id>/regenerate", methods=["POST"])
@staff("S0")
def admin_area_regenerate(area_id):
    area, before = geo.regenerate_area(area_id, request.get_json(silent=True) or {})
    record("m4l.area.regenerate", "m4l_area", area_id, {"before": before, "after": area})
    return jsonify(area)


@m4l.route("/api/m4l/admin/areas/<int:area_id>", methods=["PUT"])
@staff("S0")
def admin_area_status(area_id):
    area = geo.set_area_status(area_id, str((request.get_json(silent=True) or {}).get("status") or ""))
    record("m4l.area.status", "m4l_area", area_id, {"status": area["status"]})
    return jsonify(area)


def managed_areas():
    """Areas where the staff member may place pins: all for S0; for CONTENT, pilot areas fully inside their wards
    and city areas (each pin is then checked against the ward/commune of its cell)."""
    scope = wards()
    return [r for r in q("SELECT * FROM m4l_areas ORDER BY id")
            if scope is None or r["kind"] == "city" or set(json.loads(r["ward_slugs"])) <= scope]


def pin_in_scope(area, lat, lng):
    scope = wards()
    if scope is None or area["kind"] != "city":
        return True
    cell = geo.pin_unit(area, lat, lng)
    return bool(cell and cell["unit_slug"] in scope)


@m4l.route("/api/m4l/admin/pins", methods=["GET"])
@staff("S0", "CONTENT")
def admin_pins():
    areas = managed_areas()
    by_id = {a["id"]: a for a in areas}
    items = [p for p in geo.admin_pins(list(by_id)) if pin_in_scope(by_id[p["area_id"]], p["lat"], p["lng"])]
    return jsonify(items=items, areas=[geo.area_public(a) for a in areas])


@m4l.route("/api/m4l/admin/pins", methods=["POST"])
@staff("S0", "CONTENT")
def admin_pin_create():
    d = request.get_json(silent=True) or {}
    area = next((a for a in managed_areas() if a["slug"] == d.get("area")), None)
    if not area:
        raise svc.ServiceError("Khu vực không tồn tại hoặc ngoài phạm vi được giao", "FORBIDDEN", 403)
    pin = geo.create_pin(area, d, actor())
    if not pin_in_scope(area, pin["lat"], pin["lng"]):
        get_db().execute("DELETE FROM m4l_mystery_pins WHERE id=?", (pin["id"],))
        get_db().commit()
        raise svc.ServiceError("Vị trí ghim nằm ngoài phường/xã được giao", "FORBIDDEN", 403)
    record("m4l.pin.create", "m4l_pin", pin["id"], {"after": pin})
    return jsonify(pin), 201


@m4l.route("/api/m4l/admin/pins/<int:pin_id>", methods=["PUT"])
@staff("S0", "CONTENT")
def admin_pin_update(pin_id):
    pin = q("SELECT * FROM m4l_mystery_pins WHERE id=?", (pin_id,), one=True)
    area = next((a for a in managed_areas() if pin and a["id"] == pin["area_id"]), None)
    if not area or not pin_in_scope(area, pin["lat"], pin["lng"]):
        raise svc.ServiceError("Không tìm thấy ghim trong phạm vi được giao", "NOT_FOUND", 404)
    d = request.get_json(silent=True) or {}
    if ("lat" in d or "lng" in d) and not pin_in_scope(area, d.get("lat", pin["lat"]), d.get("lng", pin["lng"])):
        raise svc.ServiceError("Vị trí ghim nằm ngoài phường/xã được giao", "FORBIDDEN", 403)
    after = geo.update_pin(dict(pin), area, d)
    record("m4l.pin.update", "m4l_pin", pin_id, {"before": dict(pin), "after": after})
    return jsonify(after)


# ---------------------------------------------------------------- admin: city grid, zones, inspection
def _area_by_id(area_id):
    area = q("SELECT * FROM m4l_areas WHERE id=?", (area_id,), one=True)
    if not area:
        raise svc.ServiceError("Không tìm thấy khu vực", "NOT_FOUND", 404)
    return area


@m4l.route("/api/m4l/admin/areas/<int:area_id>/stats")
@staff("S0", "CONTENT")
def admin_area_stats(area_id):
    return jsonify(geo.stats(_area_by_id(area_id)))


@m4l.route("/api/m4l/admin/areas/<int:area_id>/changes")
@staff("S0", "CONTENT")
def admin_area_changes(area_id):
    _area_by_id(area_id)
    return jsonify(items=geo.changes(area_id))


@m4l.route("/api/m4l/admin/inspect", methods=["POST"])
@staff("S0", "CONTENT")
def admin_inspect():
    d = request.get_json(silent=True) or {}
    try:
        lat, lng = float(d.get("lat")), float(d.get("lng"))
    except (TypeError, ValueError):
        raise svc.ServiceError("Cần lat và lng là số", "INVALID_LOCATION") from None
    return jsonify(geo.inspect(lat, lng))


@m4l.route("/api/m4l/admin/zones")
@staff("S0", "CONTENT")
def admin_zones():
    area = geo.get_area(request.args.get("area") or None, active_only=False)
    return jsonify(items=geo.zones(area["id"]) if area else [], area=area["slug"] if area else None, can_edit=role("S0"))


@m4l.route("/api/m4l/admin/zones", methods=["POST"])
@staff("S0")
def admin_zone_create():
    d = request.get_json(silent=True) or {}
    area = geo.get_area(d.get("area") or None, active_only=False)
    if not area:
        raise svc.ServiceError("Không tìm thấy khu vực", "AREA_NOT_FOUND", 404)
    zone, change = geo.create_zone(area, d, actor())
    record("m4l.zone.create", "m4l_zone", zone["id"], {"zone": {k: zone[k] for k in ("name", "kind", "source")}, "change": change})
    return jsonify(zone=zone, change=change), 201


@m4l.route("/api/m4l/admin/zones/<int:zone_id>", methods=["PUT"])
@staff("S0")
def admin_zone_update(zone_id):
    active = (request.get_json(silent=True) or {}).get("active")
    if not isinstance(active, bool):
        raise svc.ServiceError("Cần active là true hoặc false")
    zone, change = geo.set_zone_active(zone_id, active, actor())
    record("m4l.zone.active", "m4l_zone", zone_id, {"active": active, "change": change})
    return jsonify(zone=zone, change=change)



# ---------------------------------------------------------------- partner (OWNER accounts) and voucher redemption
def _partner():
    account = g.cms_user
    poi = commerce.partner_poi(account)
    if not poi:
        raise svc.ServiceError("Tài khoản đối tác chưa được gán địa điểm", "NO_POI", 409)
    return account, poi


def _writable_partner():
    account, poi = _partner()
    if account["read_only"]:
        raise svc.ServiceError("Tài khoản chỉ có quyền xem", "FORBIDDEN", 403)
    return account, poi


@m4l.route("/api/m4l/partner/me")
@staff("OWNER")
def partner_me():
    account, poi = _partner()
    linked = [r["slug"] for r in q("SELECT m.slug FROM m4l_poi_moods pm JOIN m4l_moods m ON m.id=pm.mood_id WHERE pm.poi_id=?", (poi["id"],))]
    return jsonify(partner={"id": account["id"], "name": account["full_name"] or account["username"], "read_only": bool(account["read_only"])},
                   poi=poi | {"moods": linked}, moods=svc.list_moods(), campaigns=commerce.list_campaigns(partner_id=account["id"]),
                   kinds=commerce.KIND_LABELS, defaults={"voucher_ttl_minutes": svc.config()["voucher_default_ttl_min"]},
                   pos_adapter=commerce.POS.name, server_time=now())


@m4l.route("/api/m4l/partner/campaigns", methods=["POST"])
@staff("OWNER")
def partner_campaign_create():
    account, poi = _writable_partner()
    import m4l_demo  # campaigns created on the hosted demo are demo data, labelled as such everywhere
    campaign, _ = commerce.save_campaign(account, poi, request.get_json(silent=True) or {}, actor(), is_demo=m4l_demo.enabled())
    record("m4l.campaign.create", "m4l_campaign", campaign["id"], {"after": campaign})
    return jsonify(campaign), 201


@m4l.route("/api/m4l/partner/campaigns/<int:campaign_id>", methods=["PUT"])
@staff("OWNER")
def partner_campaign_update(campaign_id):
    account, poi = _writable_partner()
    campaign, before = commerce.save_campaign(account, poi, request.get_json(silent=True) or {}, actor(), campaign_id)
    record("m4l.campaign.update", "m4l_campaign", campaign_id, {"before": commerce.public_json(before), "after": campaign})
    return jsonify(campaign)


@m4l.route("/api/m4l/partner/campaigns/<int:campaign_id>/submit", methods=["POST"])
@staff("OWNER")
def partner_campaign_submit(campaign_id):
    account, _ = _writable_partner()
    campaign = commerce.submit_campaign(account, campaign_id)
    record("m4l.campaign.submit", "m4l_campaign", campaign_id, {"status": campaign["status"]})
    return jsonify(campaign)


@m4l.route("/api/m4l/partner/vouchers/check", methods=["POST"])
@staff("OWNER", "S0")
def partner_voucher_check():
    return jsonify(commerce.check_voucher((request.get_json(silent=True) or {}).get("code"), g.cms_user))


@m4l.route("/api/m4l/partner/vouchers/redeem", methods=["POST"])
@staff("OWNER", "S0")
def partner_voucher_redeem():
    if g.cms_user.get("read_only"):
        raise svc.ServiceError("Tài khoản chỉ có quyền xem", "FORBIDDEN", 403)
    out = commerce.redeem((request.get_json(silent=True) or {}).get("code"), g.cms_user)
    record("m4l.voucher.redeem", "m4l_voucher", out["id"], {"campaign_id": out["campaign_id"], "pos_ref": out["pos_ref"]})
    return jsonify(out)


# ---------------------------------------------------------------- admin: campaigns, kiosks, analytics
@m4l.route("/api/m4l/admin/campaigns")
@staff("S0", "AREA")
def admin_campaigns():
    status = request.args.get("status") or None
    return jsonify(items=commerce.list_campaigns(scope=wards(), status=status))


@m4l.route("/api/m4l/admin/campaigns/<int:campaign_id>/review", methods=["POST"])
@staff("S0", "AREA")
def admin_campaign_review(campaign_id):
    d = request.get_json(silent=True) or {}
    campaign, before = commerce.review_campaign(campaign_id, str(d.get("action") or ""), d.get("note"), actor(), wards())
    record("m4l.campaign.review", "m4l_campaign", campaign_id,
           {"action": d.get("action"), "before": before["status"], "after": campaign["status"], "note": campaign["review_note"]})
    return jsonify(campaign)


@m4l.route("/api/m4l/admin/kiosks")
@staff("S0", "AREA")
def admin_kiosks():
    return jsonify(items=commerce.kiosks(wards()), radius_m=svc.config()["kiosk_radius_m"])


def _kiosk_in_scope(device_id):
    row = q("SELECT id, ward_slug FROM devices WHERE id=?", (device_id,), one=True)
    scope = wards()
    if not row or (scope is not None and row["ward_slug"] not in scope):
        raise svc.ServiceError("Không tìm thấy kiosk trong phạm vi được giao", "NOT_FOUND", 404)
    return row


@m4l.route("/api/m4l/admin/kiosks/<int:device_id>/key", methods=["POST"])
@staff("S0", "AREA")
def admin_kiosk_key(device_id):
    _kiosk_in_scope(device_id)
    key = commerce.issue_kiosk_key(device_id, actor())
    record("m4l.kiosk.key_issue", "device", device_id, {"prefix": key[:9]})
    return jsonify(key=key, note="Khóa chỉ hiển thị một lần. Nhập vào màn hình trạm /m4l/station."), 201


@m4l.route("/api/m4l/admin/kiosks/<int:device_id>/key", methods=["DELETE"])
@staff("S0", "AREA")
def admin_kiosk_key_revoke(device_id):
    _kiosk_in_scope(device_id)
    commerce.revoke_kiosk_key(device_id)
    record("m4l.kiosk.key_revoke", "device", device_id, {})
    return jsonify(ok=True)


@m4l.route("/api/m4l/admin/analytics")
@staff("S0", "AREA")
def admin_analytics():
    days = svc._int(request.args.get("days"), "days", 1, 365, 30)
    return jsonify(commerce.overview(wards(), days))
