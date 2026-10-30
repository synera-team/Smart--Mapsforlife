"""M4L 2.0 commerce: partner campaigns (mood sponsorship, VIP random pool, kiosk O2O),
Pioneer vouchers with a server-side countdown, kiosk check-in tickets and the analytics funnel.

Partners are the existing OWNER accounts and the POI currently assigned to them
(cms_assignments); kiosks are rows of `devices`. Nothing here moves money: campaigns hold
contract data, approval is manual, and POS confirmation goes through an adapter whose only
implementation is a mock until a real POS API is approved.
"""
import hashlib
import hmac
import json
import secrets

from db import IS_PG, now, q
from geoutil import haversine_m
import m4l_service as svc
from m4l_service import ServiceError, transaction

KINDS = ("mood_sponsor", "vip_spin", "kiosk_o2o")
KIND_LABELS = {"mood_sponsor": "Tài trợ mood", "vip_spin": "Random VIP", "kiosk_o2o": "Kiosk O2O"}
REVIEW_ACTIONS = {"approve": ("pending",), "reject": ("pending",), "pause": ("approved",), "resume": ("paused",),
                  "end": ("approved", "paused", "pending", "draft")}
CLIENT_EVENTS = ("nav_click", "detail_view")
FUNNEL = ("impression", "qr_scan", "claim", "nav_click", "redeem")
SOURCES = ("discovery", "random", "home", "kiosk", "pin")
MAX_CAMPAIGN_DAYS = 366


# ---------------------------------------------------------------- POS adapter
class MockPOS:
    """Stands in for a partner POS until a real API and credentials are approved (D9)."""
    name = "mock"

    def confirm(self, voucher):
        return f"MOCK-{voucher['id']}-{secrets.token_hex(3).upper()}"


POS = MockPOS()


# ---------------------------------------------------------------- helpers
def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _bool(value):
    return value in (True, 1, "1", "true", "on")


def log_event(conn, kind, *, account_id=None, campaign_id=None, poi_id=None, device_id=None, voucher_id=None, source="", event_id=None):
    conn.execute("INSERT INTO m4l_events(event_id,type,account_id,campaign_id,poi_id,device_id,voucher_id,source,created_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO NOTHING",
                 (event_id, kind, account_id, campaign_id, poi_id, device_id, voucher_id, source, now()))


def partner_poi(account):
    """The POI an OWNER account currently manages, or None."""
    row = q("SELECT p.id, p.name, p.lat, p.lng, p.ward_slug, p.address FROM cms_assignments ca JOIN pois p ON p.id=ca.poi_id "
            "WHERE ca.account_id=? AND ca.released_at IS NULL", (account["id"],), one=True)
    return dict(row) if row else None


def within(campaign, location):
    """Geographic scope: no radius = whole city; otherwise the user must be inside the circle."""
    if not campaign["radius_m"]:
        return True
    if not location:
        return False
    return haversine_m(location[0], location[1], campaign["center_lat"], campaign["center_lng"]) <= campaign["radius_m"]


# ---------------------------------------------------------------- campaign data
def _epoch(value, name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ServiceError(f"{name} phải là thời điểm (giây epoch)") from None
    if number < 1_600_000_000 or number > 4_000_000_000:
        raise ServiceError(f"{name} không hợp lệ")
    return number


def campaign_fields(d, poi, existing=None):
    """Validate a create/update payload. `poi` is the partner's POI (or the chosen POI for S0)."""
    base = dict(existing or {})
    kind = str(d.get("kind", base.get("kind")) or "")
    if kind not in KINDS:
        raise ServiceError("Loại chiến dịch phải là mood_sponsor, vip_spin hoặc kiosk_o2o")
    out = {"kind": kind, "poi_id": poi["id"]}
    out["name"] = svc._text(d.get("name", base.get("name")), "tên chiến dịch", 120, required=True)
    mood_slug = d.get("mood", None)
    if mood_slug is None and existing:
        out["mood_id"] = base.get("mood_id")
    elif mood_slug:
        mood = q("SELECT id FROM m4l_moods WHERE slug=?", (str(mood_slug),), one=True)
        if not mood:
            raise ServiceError("Mood không tồn tại", "MOOD_NOT_FOUND", 404)
        out["mood_id"] = mood["id"]
    else:
        out["mood_id"] = None
    if kind == "mood_sponsor" and not out["mood_id"]:
        raise ServiceError("Chiến dịch tài trợ mood cần chọn mood")
    radius = d.get("radius_m", base.get("radius_m"))
    out["radius_m"] = svc._int(radius, "radius_m", 100, 50000)
    out["center_lat"], out["center_lng"] = (poi["lat"], poi["lng"]) if out["radius_m"] else (None, None)
    out["starts_at"] = _epoch(d.get("starts_at", base.get("starts_at")), "Thời điểm bắt đầu")
    out["ends_at"] = _epoch(d.get("ends_at", base.get("ends_at")), "Thời điểm kết thúc")
    if out["ends_at"] <= out["starts_at"]:
        raise ServiceError("Thời điểm kết thúc phải sau thời điểm bắt đầu")
    if out["ends_at"] - out["starts_at"] > MAX_CAMPAIGN_DAYS * 86400:
        raise ServiceError(f"Chiến dịch tối đa {MAX_CAMPAIGN_DAYS} ngày")
    out["priority"] = svc._int(d.get("priority", base.get("priority")), "priority", 0, 100, 0)
    out["package"] = svc._text(d.get("package", base.get("package")), "gói tài trợ", 80)
    out["exclusive"] = 1 if kind == "mood_sponsor" and _bool(d.get("exclusive", base.get("exclusive"))) else 0
    out["impression_cap"] = svc._int(d.get("impression_cap", base.get("impression_cap")), "impression_cap", 1, 10_000_000)
    return out


def voucher_fields(v, ttl_default):
    if not isinstance(v, dict):
        raise ServiceError("Thông tin voucher không hợp lệ")
    return {"title": svc._text(v.get("title"), "tên voucher", 120, required=True),
            "benefit": svc._text(v.get("benefit"), "ưu đãi", 200, required=True),
            "terms": svc._text(v.get("terms"), "điều kiện", 500),
            "ttl_minutes": svc._int(v.get("ttl_minutes"), "ttl_minutes", 5, 1440, ttl_default),
            "issue_cap": svc._int(v.get("issue_cap"), "issue_cap", 1, 1_000_000, None) or _missing("issue_cap"),
            "per_user_cap": svc._int(v.get("per_user_cap"), "per_user_cap", 1, 10, 1),
            "status": "inactive" if v.get("status") == "inactive" else "active"}


def _missing(name):
    raise ServiceError(f"Cần nhập {name} (hạn mức phát hành)")


def campaign_public(row, template=None, stats=None):
    out = {k: row[k] for k in ("id", "kind", "name", "partner_account_id", "poi_id", "mood_id", "center_lat", "center_lng", "radius_m",
                               "starts_at", "ends_at", "priority", "package", "exclusive", "impression_cap", "status", "is_demo",
                               "review_note", "reviewed_by", "reviewed_at", "created_at", "updated_at")}
    out["kind_label"] = KIND_LABELS[row["kind"]]
    for key in ("poi_name", "partner_name", "mood_name", "ward_slug"):
        if key in row.keys():
            out[key] = row[key]
    out["live"] = row["status"] == "approved" and row["starts_at"] <= now() < row["ends_at"]
    if template is not None:
        out["voucher"] = template_public(template) if template else None
    if stats is not None:
        out["stats"] = stats
    return out


def template_public(t):
    return {k: t[k] for k in ("id", "title", "benefit", "terms", "ttl_minutes", "issue_cap", "per_user_cap", "issued_count", "status")} | {
        "remaining": max(0, t["issue_cap"] - t["issued_count"])}


CAMPAIGN_SELECT = ("SELECT c.*, p.name AS poi_name, p.ward_slug, a.full_name AS partner_name, m.name AS mood_name FROM m4l_campaigns c "
                   "JOIN pois p ON p.id=c.poi_id LEFT JOIN cms_accounts a ON a.id=c.partner_account_id "
                   "LEFT JOIN m4l_moods m ON m.id=c.mood_id")


def _templates(ids):
    if not ids:
        return {}
    rows = q(f"SELECT * FROM m4l_voucher_templates WHERE campaign_id IN ({','.join('?' * len(ids))})", tuple(ids))
    return {r["campaign_id"]: r for r in rows}


def list_campaigns(partner_id=None, scope=None, status=None):
    sql, args = CAMPAIGN_SELECT + " WHERE 1=1", []
    if partner_id is not None:
        sql += " AND c.partner_account_id=?"
        args.append(partner_id)
    if status:
        sql += " AND c.status=?"
        args.append(status)
    rows = [r for r in q(sql + " ORDER BY c.id DESC", args) if scope is None or r["ward_slug"] in scope]
    templates = _templates([r["id"] for r in rows])
    stats = funnel([r["id"] for r in rows])
    return [campaign_public(r, templates.get(r["id"], False), stats.get(r["id"])) for r in rows]


def get_campaign(campaign_id):
    row = q(CAMPAIGN_SELECT + " WHERE c.id=?", (campaign_id,), one=True)
    if not row:
        raise ServiceError("Không tìm thấy chiến dịch", "NOT_FOUND", 404)
    return row


def save_campaign(partner, poi, d, actor, campaign_id=None, is_demo=False):
    """Partner create/update. Only draft or rejected campaigns can be edited; editing sends a rejected one back to draft."""
    cfg = svc.config()
    existing = None
    if campaign_id is not None:
        existing = get_campaign(campaign_id)
        if existing["partner_account_id"] != partner["id"]:
            raise ServiceError("Không tìm thấy chiến dịch", "NOT_FOUND", 404)
        if existing["status"] not in ("draft", "rejected"):
            raise ServiceError("Chỉ sửa được chiến dịch nháp hoặc bị từ chối", "INVALID_STATE", 409)
    fields = campaign_fields(d, poi, existing)
    voucher = voucher_fields(d["voucher"], cfg["voucher_default_ttl_min"]) if d.get("voucher") else None
    t = now()
    with transaction() as conn:
        if existing is None:
            cur = conn.execute(
                "INSERT INTO m4l_campaigns(kind,name,partner_account_id,poi_id,mood_id,center_lat,center_lng,radius_m,starts_at,ends_at,"
                "priority,package,exclusive,impression_cap,status,is_demo,created_by,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?,?)",
                (fields["kind"], fields["name"], partner["id"], fields["poi_id"], fields["mood_id"], fields["center_lat"], fields["center_lng"],
                 fields["radius_m"], fields["starts_at"], fields["ends_at"], fields["priority"], fields["package"], fields["exclusive"],
                 fields["impression_cap"], 1 if is_demo else 0, actor, t, t))
            campaign_id = cur.lastrowid
        else:
            conn.execute(f"UPDATE m4l_campaigns SET {','.join(k + '=?' for k in fields)}, status='draft', updated_at=? WHERE id=?",
                         (*fields.values(), t, campaign_id))
        if voucher:
            if conn.execute("SELECT 1 FROM m4l_voucher_templates WHERE campaign_id=?", (campaign_id,)).fetchone():
                conn.execute(f"UPDATE m4l_voucher_templates SET {','.join(k + '=?' for k in voucher)}, updated_at=? WHERE campaign_id=?",
                             (*voucher.values(), t, campaign_id))
            else:
                conn.execute("INSERT INTO m4l_voucher_templates(campaign_id,title,benefit,terms,ttl_minutes,issue_cap,per_user_cap,status,created_at,updated_at) "
                             "VALUES(?,?,?,?,?,?,?,?,?,?)", (campaign_id, voucher["title"], voucher["benefit"], voucher["terms"],
                                                             voucher["ttl_minutes"], voucher["issue_cap"], voucher["per_user_cap"], voucher["status"], t, t))
    row = get_campaign(campaign_id)
    return campaign_public(row, _templates([campaign_id]).get(campaign_id, False)), (dict(existing) if existing else None)


def _mood_linked(row):
    return bool(q("SELECT 1 FROM m4l_poi_moods WHERE poi_id=? AND mood_id=?", (row["poi_id"], row["mood_id"]), one=True))


def submit_campaign(partner, campaign_id):
    row = get_campaign(campaign_id)
    if row["partner_account_id"] != partner["id"]:
        raise ServiceError("Không tìm thấy chiến dịch", "NOT_FOUND", 404)
    if row["status"] not in ("draft", "rejected"):
        raise ServiceError("Chiến dịch đã được gửi duyệt", "INVALID_STATE", 409)
    if row["ends_at"] <= now():
        raise ServiceError("Chiến dịch đã quá thời điểm kết thúc", "CAMPAIGN_EXPIRED", 409)
    svc._execute("UPDATE m4l_campaigns SET status='pending', updated_at=? WHERE id=?", (now(), campaign_id))
    return campaign_public(get_campaign(campaign_id), _templates([campaign_id]).get(campaign_id, False))


def _overlaps(a, b):
    if a["starts_at"] >= b["ends_at"] or b["starts_at"] >= a["ends_at"]:
        return False
    if not a["radius_m"] or not b["radius_m"]:
        return True
    return haversine_m(a["center_lat"], a["center_lng"], b["center_lat"], b["center_lng"]) < a["radius_m"] + b["radius_m"]


def exclusivity_conflict(row):
    """Another approved sponsorship of the same mood that overlaps in time and space, where either side is exclusive."""
    if row["kind"] != "mood_sponsor":
        return None
    others = q("SELECT * FROM m4l_campaigns WHERE kind='mood_sponsor' AND status IN ('approved','paused') AND mood_id=? AND id<>?",
               (row["mood_id"], row["id"]))
    for other in others:
        if (row["exclusive"] or other["exclusive"]) and _overlaps(row, other):
            return other
    return None


def review_campaign(campaign_id, action, note, actor, scope):
    row = get_campaign(campaign_id)
    if scope is not None and row["ward_slug"] not in scope:
        raise ServiceError("Không tìm thấy chiến dịch trong phạm vi được giao", "NOT_FOUND", 404)
    if action not in REVIEW_ACTIONS:
        raise ServiceError("Thao tác phải là approve, reject, pause, resume hoặc end")
    if row["status"] not in REVIEW_ACTIONS[action]:
        raise ServiceError(f"Không thể {action} chiến dịch đang ở trạng thái {row['status']}", "INVALID_STATE", 409)
    note = svc._text(note, "ghi chú", 500, required=action == "reject")
    if action in ("approve", "resume"):
        if row["ends_at"] <= now():
            raise ServiceError("Chiến dịch đã hết hạn", "CAMPAIGN_EXPIRED", 409)
        partner = q("SELECT active FROM cms_accounts WHERE id=?", (row["partner_account_id"],), one=True)
        if not partner or not partner["active"]:
            raise ServiceError("Tài khoản đối tác đang bị khóa", "PARTNER_LOCKED", 409)
        if row["kind"] == "mood_sponsor" and not _mood_linked(row):
            raise ServiceError("Địa điểm chưa được kiểm duyệt gắn với mood này. Gắn mood tại mục Địa điểm trước khi duyệt.", "MOOD_MISMATCH", 409)
        clash = exclusivity_conflict(row)
        if clash:
            raise ServiceError(f"Trùng quyền độc quyền với chiến dịch #{clash['id']} “{clash['name']}” cùng mood, cùng thời gian và khu vực",
                               "EXCLUSIVE_CONFLICT", 409)
    status = {"approve": "approved", "reject": "rejected", "pause": "paused", "resume": "approved", "end": "ended"}[action]
    svc._execute("UPDATE m4l_campaigns SET status=?, review_note=?, reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?",
                 (status, note, actor, now(), now(), campaign_id))
    return campaign_public(get_campaign(campaign_id), _templates([campaign_id]).get(campaign_id, False)), dict(row)


# ---------------------------------------------------------------- live selection
def live_campaigns(kind, poi_ids=None):
    """Approved, in schedule, partner active and still managing the POI, POI publicly visible, impression cap not reached."""
    t = now()
    sql = (CAMPAIGN_SELECT + " JOIN cms_accounts pa ON pa.id=c.partner_account_id AND pa.active=1 "
           "WHERE c.kind=? AND c.status='approved' AND c.starts_at<=? AND c.ends_at>? AND " + svc.VISIBLE +
           " AND EXISTS (SELECT 1 FROM cms_assignments ca WHERE ca.poi_id=c.poi_id AND ca.account_id=c.partner_account_id AND ca.released_at IS NULL)")
    args = [kind, t, t, t]
    if kind == "mood_sponsor":
        sql += (" AND EXISTS (SELECT 1 FROM m4l_moods mm WHERE mm.id=c.mood_id AND mm.status='active')"
                " AND EXISTS (SELECT 1 FROM m4l_poi_moods pm WHERE pm.poi_id=c.poi_id AND pm.mood_id=c.mood_id)")
    if poi_ids is not None:
        if not poi_ids:
            return []
        sql += f" AND c.poi_id IN ({','.join('?' * len(poi_ids))})"
        args += list(poi_ids)
    rows = q(sql, args)
    capped = [r["id"] for r in rows if r["impression_cap"]]
    if capped:
        seen = {r["campaign_id"]: r["n"] for r in q(
            f"SELECT campaign_id, COUNT(*) AS n FROM m4l_events WHERE type='impression' AND campaign_id IN ({','.join('?' * len(capped))}) "
            "GROUP BY campaign_id", tuple(capped))}
        rows = [r for r in rows if not r["impression_cap"] or seen.get(r["id"], 0) < r["impression_cap"]]
    return rows


def _offer(template, campaign):
    if not template or template["status"] != "active" or template["issued_count"] >= template["issue_cap"]:
        return None
    return {"campaign_id": campaign["id"], "title": template["title"], "benefit": template["benefit"], "terms": template["terms"],
            "ttl_minutes": template["ttl_minutes"], "remaining": template["issue_cap"] - template["issued_count"],
            "sponsored": True, "partner": campaign["poi_name"], "is_demo": bool(campaign["is_demo"])}


def offers_for_pois(poi_ids):
    """poi_id → voucher offer from a live discovery campaign (mood sponsorship or VIP). Kiosk vouchers need a kiosk check-in."""
    rows = [r for kind in ("mood_sponsor", "vip_spin") for r in live_campaigns(kind, poi_ids)]
    templates = _templates([r["id"] for r in rows])
    out = {}
    for r in sorted(rows, key=lambda r: (-r["priority"], r["id"])):
        offer = _offer(templates.get(r["id"]), r)
        if offer and r["poi_id"] not in out:
            out[r["poi_id"]] = offer
    return out


def attach_offers(items):
    offers = offers_for_pois([i["id"] for i in items])
    for item in items:
        item["offer"] = offers.get(item["id"])
    return items


def impression(conn, viewer, campaign, poi_id, source):
    """Deduplicated per viewer, campaign and 10-minute window so a refresh does not inflate the count."""
    bucket = now() // 600
    log_event(conn, "impression", account_id=viewer.get("account_id"), campaign_id=campaign, poi_id=poi_id, source=source,
              event_id=f"imp:{viewer['key']}:{campaign}:{bucket}")


def sponsor_for(mood, location, viewer):
    """At most one labelled sponsored item for a mood; highest contract priority wins, then the oldest approval."""
    rows = [r for r in live_campaigns("mood_sponsor") if r["mood_id"] == mood["id"] and within(r, location)]
    if not rows:
        return None
    best = sorted(rows, key=lambda r: (-r["priority"], r["reviewed_at"] or 0, r["id"]))[0]
    poi = q("SELECT p.*, c.name AS category_name, w.name AS ward_name FROM pois p LEFT JOIN categories c ON c.id=p.category "
            "LEFT JOIN wards w ON w.slug=p.ward_slug WHERE p.id=?", (best["poi_id"],), one=True)
    distance = haversine_m(location[0], location[1], poi["lat"], poi["lng"]) if location else None
    item = svc._item(poi, distance, svc._mood_links([poi["id"]]), mood)
    item.update(sponsored=True, sponsor_label="Tài trợ", campaign_id=best["id"],
                sponsor_reason=f"Đối tác tài trợ mood “{mood['name']}”" + (" trong khu vực của bạn" if best["radius_m"] else ""))
    with transaction() as conn:
        impression(conn, viewer, best["id"], poi["id"], "discovery")
    return item


def vip_pool(scored, location):
    """VIP random pool: live vip_spin campaigns whose POI passed the user's filters; only the top paid tier of the day enters."""
    by_poi = {s[0]["id"]: s for s in scored}
    rows = [r for r in live_campaigns("vip_spin", list(by_poi)) if within(r, location)]
    if not rows:
        return []
    top = max(r["priority"] for r in rows)
    return [(r, by_poi[r["poi_id"]]) for r in rows if r["priority"] == top]


# ---------------------------------------------------------------- vouchers
def voucher_public(row, with_code=True):
    t = now()
    status = "expired" if row["status"] == "issued" and row["expires_at"] <= t else row["status"]
    out = {"id": row["id"], "status": status, "issued_at": row["issued_at"], "expires_at": row["expires_at"],
           "seconds_left": max(0, row["expires_at"] - t) if status == "issued" else 0, "source": row["source"],
           "redeemed_at": row["redeemed_at"], "campaign_id": row["campaign_id"], "poi_id": row["poi_id"]}
    for key in ("title", "benefit", "terms", "poi_name", "poi_address", "lat", "lng", "is_demo"):
        if key in row.keys():
            out[key] = row[key]
    if with_code and status == "issued":
        out["code"] = row["code"]  # the QR payload disappears as soon as the voucher is no longer usable
    return out


VOUCHER_SELECT = ("SELECT v.*, t.title, t.benefit, t.terms, p.name AS poi_name, p.address AS poi_address, p.lat, p.lng, c.is_demo "
                  "FROM m4l_vouchers v JOIN m4l_voucher_templates t ON t.id=v.template_id JOIN pois p ON p.id=v.poi_id "
                  "JOIN m4l_campaigns c ON c.id=v.campaign_id")


def expire_due():
    svc._execute("UPDATE m4l_vouchers SET status='expired' WHERE status='issued' AND expires_at<=?", (now(),))


def wallet(account_id):
    expire_due()
    rows = q(VOUCHER_SELECT + " WHERE v.account_id=? ORDER BY CASE v.status WHEN 'issued' THEN 0 ELSE 1 END, v.issued_at DESC LIMIT 50", (account_id,))
    return [voucher_public(r) for r in rows]


def claim(account_id, campaign_id, source, idem_key=None, kiosk_session_id=None):
    """Issue one voucher bound to the account. Atomic against the cap, the per-user cap and duplicate taps."""
    if source not in SOURCES:
        raise ServiceError("Nguồn nhận voucher không hợp lệ")
    if idem_key is not None and (not isinstance(idem_key, str) or not 8 <= len(idem_key) <= 64):
        raise ServiceError("Mã chống trùng không hợp lệ")
    t = now()
    with transaction() as conn:
        if IS_PG:
            conn.execute("SELECT pg_advisory_xact_lock(?)", (4260000000 + int(campaign_id),))
        if idem_key:
            same = conn.execute("SELECT id FROM m4l_vouchers WHERE account_id=? AND idempotency_key=?", (account_id, idem_key)).fetchone()
            if same:
                return {"voucher_id": same["id"], "replayed": True}
        live = {r["id"]: r for kind in KINDS for r in live_campaigns(kind) if r["id"] == campaign_id}
        campaign = live.get(campaign_id)
        if not campaign:
            raise ServiceError("Ưu đãi không còn hiệu lực", "CAMPAIGN_NOT_ACTIVE", 409)
        if campaign["kind"] == "kiosk_o2o":
            if source != "kiosk" or not kiosk_session_id:
                raise ServiceError("Ưu đãi này chỉ nhận được khi quét mã tại trạm Xanh24", "KIOSK_REQUIRED", 403)
            session = conn.execute("SELECT * FROM m4l_kiosk_sessions WHERE id=? AND account_id=?", (kiosk_session_id, account_id)).fetchone()
            if not session or t - session["used_at"] > svc.config()["kiosk_claim_window_s"]:
                raise ServiceError("Phiên check-in tại trạm đã hết hạn, hãy quét lại mã", "KIOSK_SESSION_EXPIRED", 403)
            device = conn.execute("SELECT lat, lng FROM devices WHERE id=?", (session["device_id"],)).fetchone()
            poi = conn.execute("SELECT lat, lng FROM pois WHERE id=?", (campaign["poi_id"],)).fetchone()
            if not device or device["lat"] is None or haversine_m(device["lat"], device["lng"], poi["lat"], poi["lng"]) > max(
                    campaign["radius_m"] or 0, svc.config()["kiosk_radius_m"]):
                raise ServiceError("Ưu đãi không thuộc khu vực của trạm này", "OUT_OF_KIOSK_RANGE", 403)
        template = conn.execute("SELECT * FROM m4l_voucher_templates WHERE campaign_id=?", (campaign_id,)).fetchone()
        if not template or template["status"] != "active":
            raise ServiceError("Chiến dịch này không phát hành voucher", "NO_VOUCHER", 409)
        mine = conn.execute("SELECT * FROM m4l_vouchers WHERE account_id=? AND campaign_id=? ORDER BY id DESC", (account_id, campaign_id)).fetchall()
        if len(mine) >= template["per_user_cap"]:
            active = next((v for v in mine if v["status"] == "issued" and v["expires_at"] > t), None)
            raise ServiceError("Bạn đã nhận voucher này rồi" + (" — voucher vẫn còn hạn trong ví" if active else ""), "ALREADY_CLAIMED", 409)
        taken = conn.execute("UPDATE m4l_voucher_templates SET issued_count=issued_count+1 WHERE id=? AND issued_count<issue_cap", (template["id"],))
        if taken.rowcount != 1:
            raise ServiceError("Voucher đã được nhận hết", "SOLD_OUT", 409)
        code = secrets.token_urlsafe(18)
        cur = conn.execute("INSERT INTO m4l_vouchers(code,template_id,campaign_id,account_id,poi_id,source,kiosk_session_id,idempotency_key,status,issued_at,expires_at) "
                           "VALUES(?,?,?,?,?,?,?,?,'issued',?,?)", (code, template["id"], campaign_id, account_id, campaign["poi_id"], source,
                                                                    kiosk_session_id, idem_key, t, t + template["ttl_minutes"] * 60))
        voucher_id = cur.lastrowid
        log_event(conn, "claim", account_id=account_id, campaign_id=campaign_id, poi_id=campaign["poi_id"], voucher_id=voucher_id,
                  device_id=None, source=source)
    return {"voucher_id": voucher_id, "replayed": False}


def voucher_by_id(account_id, voucher_id):
    row = q(VOUCHER_SELECT + " WHERE v.id=? AND v.account_id=?", (voucher_id, account_id), one=True)
    if not row:
        raise ServiceError("Không tìm thấy voucher", "NOT_FOUND", 404)
    return voucher_public(row)


def _staff_voucher(code, staff):
    """Voucher row visible to this staff member: S0 sees all, an OWNER only vouchers for the POI it manages."""
    if not isinstance(code, str) or not 10 <= len(code) <= 64:
        raise ServiceError("Mã voucher không hợp lệ", "NOT_FOUND", 404)
    row = q(VOUCHER_SELECT + " WHERE v.code=?", (code.strip(),), one=True)
    if row and staff["role"] == "OWNER":
        poi = partner_poi(staff)
        if not poi or poi["id"] != row["poi_id"]:
            row = None
    if not row:
        raise ServiceError("Không tìm thấy voucher của cửa hàng bạn", "NOT_FOUND", 404)
    return row


def check_voucher(code, staff):
    return voucher_public(_staff_voucher(code, staff), with_code=False)


def redeem(code, staff):
    row = _staff_voucher(code, staff)
    t = now()
    with transaction() as conn:
        current = conn.execute("SELECT * FROM m4l_vouchers WHERE id=?", (row["id"],)).fetchone()
        if current["status"] == "redeemed":
            raise ServiceError("Voucher đã được sử dụng", "ALREADY_REDEEMED", 409)
        if current["status"] == "revoked":
            raise ServiceError("Voucher đã bị thu hồi", "REVOKED", 410)
        if current["status"] == "expired" or current["expires_at"] <= t:
            conn.execute("UPDATE m4l_vouchers SET status='expired' WHERE id=? AND status='issued'", (row["id"],))
            raise ServiceError("Voucher đã hết hạn", "EXPIRED", 410)
        ref = POS.confirm(dict(current))
        done = conn.execute("UPDATE m4l_vouchers SET status='redeemed', redeemed_at=?, redeemed_by=?, redeem_ref=? "
                            "WHERE id=? AND status='issued' AND expires_at>?", (t, staff["username"], ref, row["id"], t))
        if done.rowcount != 1:
            raise ServiceError("Voucher đã được sử dụng", "ALREADY_REDEEMED", 409)
        log_event(conn, "redeem", account_id=current["account_id"], campaign_id=current["campaign_id"], poi_id=current["poi_id"],
                  voucher_id=current["id"], source=POS.name)
    out = voucher_public(q(VOUCHER_SELECT + " WHERE v.id=?", (row["id"],), one=True), with_code=False)
    return out | {"pos": POS.name, "pos_ref": ref}


# ---------------------------------------------------------------- kiosk check-in
def issue_kiosk_key(device_id, actor):
    key = "x24k_" + secrets.token_urlsafe(24)
    t = now()
    with transaction() as conn:
        conn.execute("DELETE FROM m4l_kiosk_keys WHERE device_id=?", (device_id,))
        conn.execute("INSERT INTO m4l_kiosk_keys(device_id,key_hash,key_prefix,created_by,created_at) VALUES(?,?,?,?,?)",
                     (device_id, _hash(key), key[:9], actor, t))
    return key


def revoke_kiosk_key(device_id):
    svc._execute("UPDATE m4l_kiosk_keys SET revoked_at=? WHERE device_id=? AND revoked_at IS NULL", (now(), device_id))


def kiosk_device(code, key):
    device = q("SELECT d.*, k.key_hash, k.revoked_at FROM devices d JOIN m4l_kiosk_keys k ON k.device_id=d.id WHERE d.code=?", (str(code or ""),), one=True)
    if not device or device["revoked_at"] or not isinstance(key, str) or not hmac.compare_digest(device["key_hash"], _hash(key)):
        raise ServiceError("Kiosk chưa được cấp khóa hoặc khóa không đúng", "KIOSK_UNAUTHORIZED", 401)
    if not device["active"]:
        raise ServiceError("Kiosk đang tạm ngưng", "KIOSK_DISABLED", 403)
    if device["lat"] is None:
        raise ServiceError("Kiosk chưa có tọa độ đã xác minh", "KIOSK_NO_LOCATION", 409)
    return device


def kiosk_ticket(code, key, current=None):
    """Short-lived single-use check-in token for the kiosk's QR. Re-sends the current one while it is unused and valid."""
    cfg = svc.config()
    device = kiosk_device(code, key)
    t = now()
    if isinstance(current, str) and current:
        row = q("SELECT * FROM m4l_kiosk_sessions WHERE token_hash=? AND device_id=?", (_hash(current), device["id"]), one=True)
        if row and row["used_at"] is None and row["expires_at"] - t > 15:
            return {"token": current, "expires_at": row["expires_at"], "reused": True}
    with transaction() as conn:
        recent = conn.execute("SELECT COUNT(*) AS n FROM m4l_kiosk_sessions WHERE device_id=? AND created_at>?", (device["id"], t - 60)).fetchone()["n"]
        if recent >= cfg["kiosk_tickets_per_min"]:
            raise ServiceError("Kiosk yêu cầu mã quá nhanh", "RATE_LIMITED", 429)
        token = secrets.token_urlsafe(24)
        conn.execute("INSERT INTO m4l_kiosk_sessions(token_hash,device_id,created_at,expires_at) VALUES(?,?,?,?)",
                     (_hash(token), device["id"], t, t + cfg["kiosk_ticket_ttl_s"]))
    return {"token": token, "expires_at": t + cfg["kiosk_ticket_ttl_s"], "reused": False,
            "kiosk": {"code": device["code"], "name": device["name"]}}


def kiosk_checkin(account_id, token):
    if not isinstance(token, str) or not 20 <= len(token) <= 64:
        raise ServiceError("Mã check-in không hợp lệ", "INVALID_TICKET", 404)
    t = now()
    with transaction() as conn:
        row = conn.execute("SELECT * FROM m4l_kiosk_sessions WHERE token_hash=?", (_hash(token),)).fetchone()
        if not row:
            raise ServiceError("Mã check-in không hợp lệ", "INVALID_TICKET", 404)
        if row["used_at"] is not None and row["account_id"] != account_id:
            raise ServiceError("Mã này đã được quét. Hãy quét mã mới trên màn hình trạm.", "TICKET_USED", 409)
        if row["used_at"] is None:
            if row["expires_at"] <= t:
                raise ServiceError("Mã check-in đã hết hạn. Hãy quét mã mới trên màn hình trạm.", "TICKET_EXPIRED", 410)
            used = conn.execute("UPDATE m4l_kiosk_sessions SET used_at=?, account_id=? WHERE id=? AND used_at IS NULL", (t, account_id, row["id"]))
            if used.rowcount != 1:
                raise ServiceError("Mã này đã được quét. Hãy quét mã mới trên màn hình trạm.", "TICKET_USED", 409)
            log_event(conn, "qr_scan", account_id=account_id, device_id=row["device_id"], source="kiosk")
        device = conn.execute("SELECT * FROM devices WHERE id=?", (row["device_id"],)).fetchone()
    if not device or not device["active"]:
        raise ServiceError("Kiosk đang tạm ngưng", "KIOSK_DISABLED", 403)
    return {"session_id": row["id"], "kiosk": {"code": device["code"], "name": device["name"], "address": device["address"],
                                              "lat": device["lat"], "lng": device["lng"]},
            "offers": kiosk_offers(device, account_id)}


def kiosk_offers(device, account_id):
    radius = svc.config()["kiosk_radius_m"]
    out = []
    rows = live_campaigns("kiosk_o2o")
    templates = _templates([r["id"] for r in rows])
    with transaction() as conn:
        for r in rows:
            poi = q("SELECT lat, lng, address FROM pois WHERE id=?", (r["poi_id"],), one=True)
            distance = haversine_m(device["lat"], device["lng"], poi["lat"], poi["lng"])
            if distance > max(radius, r["radius_m"] or 0):
                continue
            offer = _offer(templates.get(r["id"]), r)
            if not offer:
                continue
            out.append(offer | {"poi_id": r["poi_id"], "poi_name": r["poi_name"], "address": poi["address"], "lat": poi["lat"], "lng": poi["lng"],
                                "distance_m": round(distance)})
            log_event(conn, "impression", account_id=account_id, campaign_id=r["id"], poi_id=r["poi_id"], device_id=device["id"], source="kiosk",
                      event_id=f"imp:kiosk:{account_id}:{r['id']}:{now() // 600}")
    return sorted(out, key=lambda o: o["distance_m"])


def kiosks(scope):
    rows = q("SELECT d.id, d.code, d.name, d.ward_slug, d.address, d.lat, d.lng, d.active, k.key_prefix, k.created_at AS key_created_at, k.revoked_at "
             "FROM devices d LEFT JOIN m4l_kiosk_keys k ON k.device_id=d.id ORDER BY d.code")
    return [dict(r) | {"has_key": bool(r["key_prefix"] and not r["revoked_at"])} for r in rows if scope is None or r["ward_slug"] in scope]


# ---------------------------------------------------------------- analytics
def client_event(viewer_account, d):
    kind = d.get("type")
    if kind not in CLIENT_EVENTS:
        raise ServiceError("Loại sự kiện không hợp lệ")
    event_id = d.get("event_id")
    if not isinstance(event_id, str) or not 8 <= len(event_id) <= 64:
        raise ServiceError("Cần event_id (8–64 ký tự) để chống ghi trùng")
    ids = {k: svc._int(d.get(k), k, 1, 2 ** 31) for k in ("campaign_id", "poi_id", "voucher_id")}
    source = d.get("source") if d.get("source") in SOURCES else ""
    with transaction() as conn:
        log_event(conn, kind, account_id=viewer_account, source=source, event_id=f"c:{event_id}", **ids)
    return {"ok": True}


def funnel(campaign_ids, since=None):
    """Counts per campaign. 'redeem' is a verified redemption at the partner, not a measured store visit."""
    if not campaign_ids:
        return {}
    marks = ",".join("?" * len(campaign_ids))
    args = list(campaign_ids)
    cond = ""
    if since:
        cond, args = " AND created_at>=?", args + [since]
    out = {cid: {k: 0 for k in FUNNEL} for cid in campaign_ids}
    for r in q(f"SELECT campaign_id, type, COUNT(*) AS n FROM m4l_events WHERE campaign_id IN ({marks}){cond} GROUP BY campaign_id, type", args):
        if r["type"] in FUNNEL:
            out[r["campaign_id"]][r["type"]] = r["n"]
    for r in q(f"SELECT campaign_id, status, COUNT(*) AS n FROM m4l_vouchers WHERE campaign_id IN ({marks}) GROUP BY campaign_id, status", tuple(campaign_ids)):
        out[r["campaign_id"]].setdefault("vouchers", {})[r["status"]] = r["n"]
    return out


def overview(scope=None, days=30):
    since = now() - days * 86400
    campaigns = list_campaigns(scope=scope)
    ids = [c["id"] for c in campaigns]
    stats = funnel(ids, since)
    totals = {k: sum(s[k] for s in stats.values()) for k in FUNNEL}
    kiosk_scans = q("SELECT COUNT(*) AS n FROM m4l_events WHERE type='qr_scan' AND created_at>=?", (since,), one=True)["n"]
    vouchers = {r["status"]: r["n"] for r in q("SELECT status, COUNT(*) AS n FROM m4l_vouchers WHERE issued_at>=? GROUP BY status", (since,))}
    by_campaign = [{"id": c["id"], "name": c["name"], "kind": c["kind"], "status": c["status"], "is_demo": c["is_demo"],
                    "poi_name": c.get("poi_name"), **stats.get(c["id"], {})} for c in campaigns]
    return {"days": days, "totals": totals | {"qr_scan": kiosk_scans}, "vouchers": vouchers, "campaigns": by_campaign,
            "note": "Lượt đổi voucher là số lần đối tác xác nhận voucher tại quầy, không phải số khách thực tế bước vào cửa hàng."}


def public_json(value):
    return json.loads(json.dumps(value, default=str))
