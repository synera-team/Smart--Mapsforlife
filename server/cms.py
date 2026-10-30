"""CMS for area managers, content reviewers and purchased map pins.

The existing S0 account is the system administrator. CMS accounts are kept in
their own table so the older S0/S1/CW admin interface continues to work.
"""
import functools
import json
import re
import time
from datetime import date

import jwt
from flask import Blueprint, g, jsonify, request

from auth import (check_password, hash_password, issue_token, login_failed,
                  login_ok, login_throttled, password_problem, secret)
from cms_registration_wards import registration_wards, valid_registration_scope
from db import ex, get_setting, now, q, row2dict, set_setting
from media import save_upload

cms = Blueprint("cms", __name__)
ROLES = {"S0": "Quản trị hệ thống", "AREA": "Nhân viên quản lí", "CONTENT": "Quản trị nội dung", "REVIEW": "Kiểm duyệt đăng kí", "OWNER": "Tài khoản kiosk", "USER": "Người dùng"}
CONTENT_FIELDS = ("name", "name_en", "description", "phone", "website", "hours", "images", "vr360", "tags")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 .()-]{7,24}$")
GENDERS = {"male", "female", "undisclosed"}


def error(message, status=400):
    return jsonify(error=message), status


def data():
    return request.get_json(silent=True) or {}


def user_details(values):
    full_name = str(values.get("full_name") or "").strip()
    email = str(values.get("email") or "").strip().lower()
    phone = str(values.get("phone") or "").strip()
    birth_date = str(values.get("birth_date") or "").strip()
    gender = str(values.get("gender") or "").strip()
    if not full_name or len(full_name) > 150 or len(email) > 200 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Cần họ tên và email hợp lệ")
    if not PHONE_PATTERN.fullmatch(phone) or not 9 <= len(re.sub(r"\D", "", phone)) <= 15:
        raise ValueError("Cần số điện thoại hợp lệ")
    try:
        born = date.fromisoformat(birth_date)
    except ValueError as exc:
        raise ValueError("Ngày sinh không hợp lệ") from exc
    if born.isoformat() != birth_date or born.year < 1900 or born > date.today():
        raise ValueError("Ngày sinh không hợp lệ")
    if gender not in GENDERS:
        raise ValueError("Cần chọn giới tính")
    return full_name, email, phone, birth_date, gender


def account_public(row):
    out = row2dict(row, ("wards",))
    out.pop("password_hash", None)
    out["role_label"] = ROLES[out["role"]]
    return out


def token_for(row):
    t = int(time.time())
    return jwt.encode({"sub": str(row["id"]), "cms": True, "iat": t, "exp": t + 12 * 3600}, secret(), algorithm="HS256")


def authenticate(fn):
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("Chưa đăng nhập", 401)
        try:
            claims = jwt.decode(header[7:], secret(), algorithms=["HS256"])
            if claims.get("cms"):
                row = q("SELECT * FROM cms_accounts WHERE id=? AND active=1", (int(claims["sub"]),), one=True)
            else:
                row = q("SELECT * FROM users WHERE id=? AND role='S0' AND active=1", (int(claims["sub"]),), one=True)
            if not row:
                return error("Tài khoản không còn hoạt động", 401)
            g.cms_user = dict(row)
        except (jwt.PyJWTError, KeyError, ValueError, TypeError):
            return error("Phiên đăng nhập không hợp lệ", 401)
        return fn(*args, **kwargs)
    return wrapped


def role(*roles):
    return g.cms_user["role"] in roles


def wards():
    if role("S0"):
        return None
    try:
        return set(json.loads(g.cms_user["wards"] or "[]"))
    except (ValueError, TypeError):
        return set()


def in_scope(ward):
    scope = wards()
    return scope is None or bool(ward and ward in scope)


def pin_row(pid):
    return q("SELECT cp.*, p.name, p.name_en, p.address, p.category, p.ward_slug, p.lat, p.lng, p.images, p.description, p.phone, p.website, p.hours, p.vr360, p.tags, "
             "ca.account_id owner_id, ca.released_at FROM cms_pins cp JOIN pois p ON p.id=cp.poi_id "
             "LEFT JOIN cms_assignments ca ON ca.poi_id=cp.poi_id AND ca.released_at IS NULL WHERE cp.poi_id=?", (pid,), one=True)


def visible_pin(row):
    if not row:
        return False
    if role("OWNER"):
        return bool(current_owner(row["poi_id"], g.cms_user["id"]))
    return in_scope(row["ward_slug"])


def pin_public(row):
    out = row2dict(row, ("images", "vr360"))
    out["live"] = bool(out["active"] and out["approved_at"] and out["expires_at"] and out["expires_at"] > now())
    return out


def current_owner(pid, account_id):
    return q("SELECT 1 FROM cms_assignments WHERE poi_id=? AND account_id=? AND released_at IS NULL", (pid, account_id), one=True)


def touch_public():
    """Signal running kiosks to refresh their public map data."""
    set_setting("config_version", max(now(), int(get_setting("config_version", 0) or 0) + 1))


def normalize_content(values):
    if not isinstance(values, dict) or not values or any(k not in CONTENT_FIELDS for k in values):
        raise ValueError("Nội dung không hợp lệ; không được thay đổi vị trí ghim")
    clean = {}
    for key, value in values.items():
        if key == "images":
            if not isinstance(value, list) or len(value) > 30 or any(
                not isinstance(image, dict) or not str(image.get("url", "")).startswith("/uploads/") for image in value
            ):
                raise ValueError("Ảnh phải là tệp đã tải lên CMS (tối đa 30 ảnh)")
        elif key == "vr360":
            if value is not None and (not isinstance(value, dict) or value.get("type") not in ("pano", "embed", "video", "tour")):
                raise ValueError("VR360 không hợp lệ")
            if value and value["type"] == "tour" and not isinstance(value.get("scenes"), list):
                raise ValueError("Danh sách cảnh VR360 không hợp lệ")
            if value and value["type"] != "tour":
                url = str(value.get("url") or "")
                if not url.startswith("https://") and not (value["type"] != "embed" and url.startswith("/uploads/")):
                    raise ValueError("VR360 cần URL HTTPS hoặc tệp tải lên")
        else:
            value = str(value or "")[:20000 if key == "description" else 500]
            if key == "name" and not value.strip():
                raise ValueError("Tên ghim không được để trống")
        clean[key] = value
    return clean


SECTION_ROLES = {"manager": ("AREA",), "admin": ("S0", "CONTENT"), "review": ("REVIEW",), "kiosk": ("OWNER",), "user": ("USER",)}


@cms.route("/api/cms/login", methods=["POST"])
def login():
    d = data()
    username = str(d.get("username") or "").strip().lower()
    section = d.get("section")
    if section not in ("manager", "admin", "review", "kiosk", "user"):
        return error("Chọn mục đăng nhập")
    key = f"cms|{request.remote_addr}|{username}"
    wait = login_throttled(key)
    if wait:
        return error(f"Thử lại sau {wait} giây", 429)
    legacy = q("SELECT * FROM users WHERE lower(username)=? AND role='S0'", (username,), one=True) if section == "admin" else None
    user = legacy or q("SELECT * FROM cms_accounts WHERE lower(username)=?", (username,), one=True)
    allowed = SECTION_ROLES[section]
    if not user or not user["active"] or not check_password(user["password_hash"], d.get("password") or ""):
        login_failed(key)
        return error("Sai tài khoản, mật khẩu hoặc mục đăng nhập", 401)
    if user["role"] not in allowed:
        # The password was right, so naming the correct tab leaks nothing and fixes the most common sign-in mistake.
        login_failed(key)
        right = next((s for s, roles in SECTION_ROLES.items() if user["role"] in roles), None)
        where = {"user": "/cms/login → Người dùng", "kiosk": "/cms/login → Tài khoản kiosk", "manager": "/hrm/login → Nhân viên quản lí",
                 "admin": "/hrm/login → Quản trị viên", "review": "/hrm/login → Kiểm duyệt đăng kí"}.get(right, "mục khác")
        return error(f"Tài khoản này đăng nhập ở mục {where}", 401)
    login_ok(key)
    table = "users" if legacy else "cms_accounts"
    ex(f"UPDATE {table} SET last_login=? WHERE id=?", (now(), user["id"]))
    return jsonify(token=issue_token(user) if legacy else token_for(user), user=account_public(user), section=section)


@cms.route("/api/cms/register", methods=["POST"])
def register_user():
    if request.content_length and request.content_length > 4096:
        return error("Thông tin đăng ký quá dài", 413)
    d = data()
    username = str(d.get("username") or "").strip().lower()
    password = str(d.get("password") or "")
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
        return error("Tên đăng nhập phải có 3–40 ký tự a-z, 0-9, . _ -")
    try:
        full_name, email, phone, birth_date, gender = user_details(d)
    except ValueError as exc:
        return error(str(exc))
    problem = password_problem(password)
    if problem:
        return error(problem)
    if q("SELECT 1 FROM cms_accounts WHERE lower(username)=?", (username,), one=True) or q(
        "SELECT 1 FROM users WHERE lower(username)=?", (username,), one=True
    ):
        return error("Tên đăng nhập đã tồn tại")
    try:
        uid = ex("INSERT INTO cms_accounts(username,password_hash,full_name,email,phone,birth_date,gender,role,wards,active,read_only,created_at) "
                 "VALUES(?,?,?,?,?,?,?,'USER','[]',1,0,?)",
                 (username, hash_password(password), full_name, email, phone, birth_date, gender, now()))
    except Exception:
        if q("SELECT 1 FROM cms_accounts WHERE lower(username)=?", (username,), one=True):
            return error("Tên đăng nhập đã tồn tại")
        raise
    row = q("SELECT * FROM cms_accounts WHERE id=?", (uid,), one=True)
    return jsonify(ok=True, token=token_for(row), user=account_public(row)), 201


@cms.route("/api/cms/me")
@authenticate
def me():
    return jsonify(user=account_public(g.cms_user))


@cms.route("/api/cms/profile", methods=["PUT"])
@authenticate
def update_profile():
    if not role("USER"):
        return error("Không có quyền", 403)
    d = data()
    try:
        full_name, email, phone, birth_date, gender = user_details(d)
    except ValueError as exc:
        return error(str(exc))
    fields = {"full_name": full_name, "email": email, "phone": phone,
              "birth_date": birth_date, "gender": gender}
    if d.get("new_password"):
        if not check_password(g.cms_user["password_hash"], str(d.get("current_password") or "")):
            return error("Mật khẩu hiện tại không đúng", 401)
        problem = password_problem(str(d["new_password"]))
        if problem:
            return error(problem)
        fields["password_hash"] = hash_password(str(d["new_password"]))
    ex(f"UPDATE cms_accounts SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), g.cms_user["id"]))
    row = q("SELECT * FROM cms_accounts WHERE id=?", (g.cms_user["id"],), one=True)
    return jsonify(ok=True, user=account_public(row))


@cms.route("/api/cms/wards")
@authenticate
def list_wards():
    if role("OWNER", "REVIEW", "USER"):
        return error("Không có quyền", 403)
    all_wards = [dict(r) for r in q("SELECT slug,name FROM wards WHERE published=1 ORDER BY name")]
    return jsonify(items=[w for w in all_wards if in_scope(w["slug"])])


@cms.route("/api/cms/registration-wards")
@authenticate
def list_registration_wards():
    if not role("S0", "REVIEW"):
        return error("Không có quyền", 403)
    scope = wards()
    return jsonify(items=[{"slug": slug, "name": name} for slug, name in registration_wards()
                          if scope is None or slug in scope])


@cms.route("/api/cms/accounts", methods=["GET", "POST"])
@authenticate
def accounts():
    if not role("S0", "AREA"):
        return error("Không có quyền", 403)
    if request.method == "GET":
        rows = [account_public(r) for r in q("SELECT * FROM cms_accounts ORDER BY id DESC")]
        if role("AREA"):
            scope = wards()
            rows = [r for r in rows if r["role"] == "OWNER" and r["wards"] and set(r["wards"]) <= scope]
        for r in rows:
            if r["role"] == "OWNER":
                assignment = q("SELECT poi_id, released_at FROM cms_assignments WHERE account_id=?", (r["id"],), one=True)
                r["pin_id"] = assignment["poi_id"] if assignment else None
                r["pin_released"] = bool(assignment and assignment["released_at"])
        return jsonify(items=rows)

    d = data()
    kind = d.get("role")
    if kind not in ("AREA", "CONTENT", "REVIEW", "OWNER", "USER") or (role("AREA") and kind != "OWNER"):
        return error("Không được cấp vai trò này", 403)
    username = str(d.get("username") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
        return error("Tên đăng nhập phải có 3–40 ký tự a-z, 0-9, . _ -")
    if q("SELECT 1 FROM cms_accounts WHERE lower(username)=?", (username,), one=True) or q("SELECT 1 FROM users WHERE lower(username)=?", (username,), one=True):
        return error("Tên đăng nhập đã tồn tại")
    problem = password_problem(d.get("password") or "")
    if problem:
        return error(problem)
    scope = d.get("wards") or []
    if not isinstance(scope, list):
        return error("Khu vực không hợp lệ")
    if kind == "USER":
        if not role("S0"):
            return error("Không được cấp vai trò này", 403)
        scope = []
    elif kind != "OWNER":
        if not role("S0") or (not valid_registration_scope(scope) if kind == "REVIEW" else
                              not scope or any(not q("SELECT 1 FROM wards WHERE slug=?", (w,), one=True) for w in scope)):
            return error("Cần chọn khu vực quản lý hợp lệ")
    else:
        from app import ward_for
        pid = d.get("pin_id")
        if pid:
            pin = pin_row(pid)
            if not pin or pin["active"] or pin["owner_id"] or not in_scope(pin["ward_slug"]):
                return error("Chỉ cấp lại được ghim đã deactive trong khu vực của bạn")
            scope = [pin["ward_slug"]]
        else:
            p = d.get("pin") or {}
            try:
                lat, lng = float(p["lat"]), float(p["lng"])
            except (KeyError, TypeError, ValueError):
                return error("Cần nhập tọa độ ghim")
            if not (8 <= lat <= 24 and 102 <= lng <= 110):
                return error("Tọa độ nằm ngoài phạm vi Việt Nam")
            ward = ward_for(lat, lng)
            if not ward or not in_scope(ward):
                return error("Ghim không thuộc khu vực được giao")
            if not str(p.get("name") or "").strip() or not q("SELECT 1 FROM categories WHERE id=?", (p.get("category"),), one=True):
                return error("Cần nhập tên và danh mục ghim")
            scope = [ward]
    t = now()
    uid = ex("INSERT INTO cms_accounts(username,password_hash,full_name,email,phone,role,wards,active,read_only,created_by,created_at) "
             "VALUES(?,?,?,?,?,?,?,1,0,?,?)",
             (username, hash_password(d["password"]), str(d.get("full_name") or "")[:150], str(d.get("email") or "")[:200],
              str(d.get("phone") or "")[:40], kind, json.dumps(scope), None if role("S0") else g.cms_user["id"], t))
    if kind == "OWNER":
        if not d.get("pin_id"):
            p = d["pin"]
            pid = ex("INSERT INTO pois(name,category,address,lat,lng,ward_slug,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'published',?,?)",
                     (str(p["name"]).strip()[:200], p["category"], str(p.get("address") or "")[:500], lat, lng, scope[0], t, t))
            ex("UPDATE pois SET code=? WHERE id=?", (f"X24-{pid:05d}", pid))
            ex("INSERT INTO cms_pins(poi_id,active,managed_by,created_at) VALUES(?,1,?,?)", (pid, None if role("S0") else g.cms_user["id"], t))
        ex("INSERT INTO cms_assignments(account_id,poi_id,assigned_at) VALUES(?,?,?)", (uid, pid, t))
    return jsonify(ok=True, id=uid, pin_id=pid if kind == "OWNER" else None)


@cms.route("/api/cms/accounts/<int:uid>", methods=["PUT"])
@authenticate
def account_update(uid):
    if not role("S0", "AREA"):
        return error("Không có quyền", 403)
    row = q("SELECT * FROM cms_accounts WHERE id=?", (uid,), one=True)
    if not row or (role("AREA") and (row["role"] != "OWNER" or not set(json.loads(row["wards"] or "[]")) <= wards())):
        return error("Không tìm thấy tài khoản trong phạm vi", 404)
    d = data()
    fields = {k: str(d[k])[:n] for k, n in (("full_name", 150), ("email", 200), ("phone", 40)) if k in d}
    if "active" in d:
        fields["active"] = 1 if d["active"] else 0
    if "wards" in d and row["role"] == "USER":
        return error("Người dùng không có khu vực phụ trách")
    if "wards" in d and role("S0") and row["role"] != "OWNER":
        scope = d["wards"]
        if (not valid_registration_scope(scope) if row["role"] == "REVIEW" else
                not isinstance(scope, list) or not scope or any(not q("SELECT 1 FROM wards WHERE slug=?", (w,), one=True) for w in scope)):
            return error("Khu vực không hợp lệ")
        fields["wards"] = json.dumps(scope)
    if d.get("password"):
        problem = password_problem(d["password"])
        if problem:
            return error(problem)
        fields["password_hash"] = hash_password(d["password"])
    if fields:
        ex(f"UPDATE cms_accounts SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), uid))
    return jsonify(ok=True)


@cms.route("/api/cms/pins")
@authenticate
def pins():
    if not role("S0", "AREA", "CONTENT", "OWNER"):
        return error("Không có quyền", 403)
    rows = q("SELECT cp.*, p.name, p.name_en, p.address, p.category, p.ward_slug, p.lat, p.lng, p.images, p.description, p.phone, p.website, p.hours, p.vr360, p.tags, "
             "ca.account_id owner_id, ca.released_at FROM cms_pins cp JOIN pois p ON p.id=cp.poi_id "
             "LEFT JOIN cms_assignments ca ON ca.poi_id=cp.poi_id AND ca.released_at IS NULL ORDER BY cp.poi_id DESC")
    return jsonify(items=[pin_public(r) for r in rows if visible_pin(r)])


@cms.route("/api/cms/pins/<int:pid>/active", methods=["POST"])
@authenticate
def pin_active(pid):
    if not role("S0", "AREA"):
        return error("Không có quyền", 403)
    row = pin_row(pid)
    if not row or not visible_pin(row):
        return error("Không tìm thấy ghim trong khu vực", 404)
    active = bool(data().get("active"))
    if active and not row["owner_id"]:
        return error("Cần cấp tài khoản mới trước khi kích hoạt ghim")
    ex("UPDATE cms_pins SET active=? WHERE poi_id=?", (int(active), pid))
    if not active and row["owner_id"]:
        # A later buyer must purchase a new package and submit their own content.
        ex("UPDATE cms_pins SET approved_at=NULL, expires_at=NULL WHERE poi_id=?", (pid,))
        ex("UPDATE cms_content SET status='rejected', review_note='Ghim đã deactive', reviewed_at=? "
           "WHERE poi_id=? AND status='pending'", (now(), pid))
        ex("UPDATE cms_assignments SET released_at=? WHERE poi_id=? AND released_at IS NULL", (now(), pid))
        ex("UPDATE cms_accounts SET read_only=1 WHERE id=?", (row["owner_id"],))
    touch_public()
    return jsonify(ok=True, active=active)


@cms.route("/api/cms/content", methods=["GET", "POST"])
@authenticate
def content():
    if request.method == "GET":
        if not role("S0", "CONTENT", "OWNER"):
            return error("Không có quyền", 403)
        status = request.args.get("status")
        rows = [row2dict(r, ("data",)) for r in q("SELECT c.*, p.ward_slug, p.name current_name FROM cms_content c JOIN pois p ON p.id=c.poi_id ORDER BY c.id DESC")]
        if role("OWNER"):
            rows = [r for r in rows if r["account_id"] == g.cms_user["id"]]
        else:
            rows = [r for r in rows if in_scope(r["ward_slug"])]
        return jsonify(items=[r for r in rows if not status or r["status"] == status])
    if not role("OWNER") or g.cms_user["read_only"]:
        return error("Tài khoản chỉ đọc", 403)
    assignment = q("SELECT a.poi_id FROM cms_assignments a JOIN cms_pins p ON p.poi_id=a.poi_id WHERE a.account_id=? AND a.released_at IS NULL AND p.active=1", (g.cms_user["id"],), one=True)
    if not assignment:
        return error("Không có ghim đang hoạt động", 403)
    d = data()
    try:
        clean = normalize_content(d.get("data") or {})
    except ValueError as exc:
        return error(str(exc))
    status = "pending" if d.get("submit") else "draft"
    t = now()
    cid = ex("INSERT INTO cms_content(poi_id,account_id,data,status,created_at,submitted_at) VALUES(?,?,?,?,?,?)",
             (assignment["poi_id"], g.cms_user["id"], json.dumps(clean, ensure_ascii=False), status, t, t if status == "pending" else None))
    return jsonify(id=cid, status=status)


@cms.route("/api/cms/content/<int:cid>", methods=["PUT"])
@authenticate
def content_update(cid):
    if not role("OWNER") or g.cms_user["read_only"]:
        return error("Tài khoản chỉ đọc", 403)
    row = q("SELECT * FROM cms_content WHERE id=? AND account_id=?", (cid, g.cms_user["id"]), one=True)
    if not row or row["status"] not in ("draft", "rejected") or not current_owner(row["poi_id"], g.cms_user["id"]):
        return error("Bản nháp không thể sửa", 403)
    try:
        clean = normalize_content(data().get("data") or {})
    except ValueError as exc:
        return error(str(exc))
    submit = bool(data().get("submit"))
    ex("UPDATE cms_content SET data=?,status=?,review_note='',submitted_at=? WHERE id=?",
       (json.dumps(clean, ensure_ascii=False), "pending" if submit else "draft", now() if submit else None, cid))
    return jsonify(ok=True, id=cid, status="pending" if submit else "draft")


@cms.route("/api/cms/content/<int:cid>/review", methods=["POST"])
@authenticate
def review(cid):
    if not role("S0", "CONTENT"):
        return error("Không có quyền duyệt", 403)
    row = q("SELECT c.*, p.ward_slug FROM cms_content c JOIN pois p ON p.id=c.poi_id WHERE c.id=?", (cid,), one=True)
    if not row or not in_scope(row["ward_slug"]):
        return error("Không tìm thấy nội dung trong khu vực", 404)
    if row["status"] != "pending":
        return error("Nội dung không ở trạng thái chờ duyệt")
    if not current_owner(row["poi_id"], row["account_id"]):
        return error("Nội dung thuộc tài khoản đã deactive", 409)
    d = data()
    action = d.get("action")
    if action not in ("approve", "reject"):
        return error("Thao tác không hợp lệ")
    note = str(d.get("note") or "").strip()[:1000]
    if action == "reject" and not note:
        return error("Cần nhập lý do từ chối")
    t = now()
    if action == "approve":
        changes = json.loads(row["data"])
        if changes:
            cols = list(changes)
            vals = [json.dumps(changes[k], ensure_ascii=False) if k in ("images", "vr360") else changes[k] for k in cols]
            ex(f"UPDATE pois SET {','.join(k + '=?' for k in cols)}, updated_at=?, version=version+1 WHERE id=?", (*vals, t, row["poi_id"]))
        ex("UPDATE cms_pins SET approved_at=? WHERE poi_id=?", (t, row["poi_id"]))
        touch_public()
    ex("UPDATE cms_content SET status=?, review_note=?, reviewed_by=?, reviewed_at=? WHERE id=?",
       ("approved" if action == "approve" else "rejected", note, g.cms_user["username"], t, cid))
    return jsonify(ok=True)


@cms.route("/api/cms/upload", methods=["POST"])
@authenticate
def upload():
    if not role("OWNER") or g.cms_user["read_only"]:
        return error("Tài khoản chỉ đọc", 403)
    f = request.files.get("file")
    if not f:
        return error("Thiếu tệp")
    try:
        return jsonify(save_upload(f.read(), f.filename, kind=request.form.get("kind", "image")))
    except (ValueError, OSError) as exc:
        return error(str(exc))


@cms.route("/api/cms/kiosks", methods=["GET", "POST"])
@authenticate
def kiosks():
    if not role("S0", "AREA"):
        return error("Không có quyền", 403)
    if request.method == "GET":
        rows = [dict(r) for r in q("SELECT id,code,name,ward_slug,address,lat,lng,active,last_seen,gps_lat,gps_lng FROM devices ORDER BY code")]
        selected = request.args.get("ward")
        return jsonify(items=[r for r in rows if in_scope(r["ward_slug"]) and (not selected or r["ward_slug"] == selected)])
    if not role("AREA"):
        return error("Admin chỉ xem danh sách kiosk", 403)
    d = data()
    if not in_scope(d.get("ward_slug")):
        return error("Kiosk ngoài khu vực quản lý", 403)
    code = str(d.get("code") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", code) or not str(d.get("name") or "").strip():
        return error("Mã hoặc tên kiosk không hợp lệ")
    if q("SELECT 1 FROM devices WHERE code=?", (code,), one=True):
        return error("Mã kiosk đã tồn tại")
    did = ex("INSERT INTO devices(code,name,ward_slug,address,lat,lng,active,created_at) VALUES(?,?,?,?,?,?,1,?)",
             (code, str(d["name"])[:150], d["ward_slug"], str(d.get("address") or "")[:300], d.get("lat"), d.get("lng"), now()))
    return jsonify(ok=True, id=did)


@cms.route("/api/cms/kiosks/<int:did>", methods=["PUT"])
@authenticate
def kiosk_update(did):
    if not role("AREA"):
        return error("Không có quyền", 403)
    row = q("SELECT * FROM devices WHERE id=?", (did,), one=True)
    if not row or not in_scope(row["ward_slug"]):
        return error("Không tìm thấy kiosk trong khu vực", 404)
    d = data()
    if "ward_slug" in d and not in_scope(d["ward_slug"]):
        return error("Không thể chuyển kiosk ra ngoài khu vực", 403)
    fields = {k: d[k] for k in ("name", "ward_slug", "address", "lat", "lng", "active") if k in d}
    if fields:
        ex(f"UPDATE devices SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), did))
    return jsonify(ok=True)


@cms.route("/api/cms/plans", methods=["GET", "POST"])
@authenticate
def plans():
    if request.method == "GET":
        return jsonify(items=[dict(r) for r in q("SELECT * FROM cms_plans ORDER BY id")])
    if not role("S0"):
        return error("Không có quyền", 403)
    d = data()
    try:
        price, days = int(d["price"]), int(d["duration_days"])
    except (KeyError, TypeError, ValueError):
        return error("Giá và thời hạn không hợp lệ")
    if not str(d.get("name") or "").strip() or price < 0 or days < 1:
        return error("Tên, giá hoặc thời hạn không hợp lệ")
    pid = ex("INSERT INTO cms_plans(name,price,duration_days,description,created_at) VALUES(?,?,?,?,?)",
             (str(d["name"])[:120], price, days, str(d.get("description") or "")[:1000], now()))
    return jsonify(ok=True, id=pid)


@cms.route("/api/cms/plans/<int:pid>", methods=["PUT"])
@authenticate
def plan_update(pid):
    if not role("S0"):
        return error("Không có quyền", 403)
    if not q("SELECT 1 FROM cms_plans WHERE id=?", (pid,), one=True):
        return error("Không tìm thấy gói", 404)
    d = data()
    fields = {k: d[k] for k in ("name", "description") if k in d}
    for k in ("price", "duration_days"):
        if k in d:
            try:
                fields[k] = int(d[k])
            except (TypeError, ValueError):
                return error("Giá hoặc thời hạn không hợp lệ")
    if "price" in fields and fields["price"] < 0 or "duration_days" in fields and fields["duration_days"] < 1:
        return error("Giá hoặc thời hạn không hợp lệ")
    if fields:
        ex(f"UPDATE cms_plans SET {','.join(k + '=?' for k in fields)} WHERE id=?", (*fields.values(), pid))
    return jsonify(ok=True)


@cms.route("/api/cms/orders", methods=["GET", "POST"])
@authenticate
def orders():
    if request.method == "GET":
        rows = [dict(r) for r in q("SELECT o.*, p.name plan_name, x.ward_slug, a.username FROM cms_orders o "
                                  "JOIN cms_plans p ON p.id=o.plan_id JOIN pois x ON x.id=o.poi_id "
                                  "JOIN cms_accounts a ON a.id=o.account_id ORDER BY o.id DESC")]
        if role("OWNER"):
            rows = [r for r in rows if r["account_id"] == g.cms_user["id"]]
        elif not role("S0", "AREA"):
            return error("Không có quyền", 403)
        else:
            rows = [r for r in rows if in_scope(r["ward_slug"])]
        return jsonify(items=rows)
    if not role("OWNER") or g.cms_user["read_only"]:
        return error("Tài khoản chỉ đọc", 403)
    owner = q("SELECT a.poi_id FROM cms_assignments a JOIN cms_pins p ON p.poi_id=a.poi_id "
              "WHERE a.account_id=? AND a.released_at IS NULL AND p.active=1", (g.cms_user["id"],), one=True)
    plan = q("SELECT * FROM cms_plans WHERE id=?", (data().get("plan_id"),), one=True)
    if not owner or not plan:
        return error("Ghim hoặc gói không hợp lệ")
    oid = ex("INSERT INTO cms_orders(account_id,poi_id,plan_id,amount,duration_days,status,created_at) VALUES(?,?,?,?,?,'pending',?)",
             (g.cms_user["id"], owner["poi_id"], plan["id"], plan["price"], plan["duration_days"], now()))
    return jsonify(id=oid, status="pending")


@cms.route("/api/cms/orders/<int:oid>/demo-pay", methods=["POST"])
@authenticate
def demo_pay(oid):
    if not role("OWNER", "S0") or (role("OWNER") and g.cms_user["read_only"]):
        return error("Không có quyền", 403)
    order = q("SELECT * FROM cms_orders WHERE id=?", (oid,), one=True)
    if not order or (role("OWNER") and order["account_id"] != g.cms_user["id"]) or not current_owner(order["poi_id"], order["account_id"]):
        return error("Không tìm thấy đơn đang sở hữu", 404)
    if order["status"] == "paid":
        return jsonify(ok=True, status="paid")
    if order["status"] != "pending":
        return error("Đơn không thể thanh toán")
    pin = pin_row(order["poi_id"])
    if not pin or not pin["active"]:
        return error("Ghim đang deactive")
    t = now()
    expiry = max(t, pin["expires_at"] or 0) + order["duration_days"] * 86400
    ex("INSERT INTO cms_payments(order_id,amount,method,reference,paid_at) VALUES(?,?,'demo',?,?)",
       (oid, order["amount"], f"DEMO-{oid:06d}", t))
    ex("UPDATE cms_orders SET status='paid',paid_at=? WHERE id=?", (t, oid))
    ex("UPDATE cms_pins SET expires_at=? WHERE poi_id=?", (expiry, order["poi_id"]))
    touch_public()
    return jsonify(ok=True, status="paid", expires_at=expiry)


@cms.route("/api/cms/orders/<int:oid>/cancel", methods=["POST"])
@authenticate
def cancel_order(oid):
    if not role("S0"):
        return error("Chỉ Admin được hủy đơn", 403)
    order = q("SELECT * FROM cms_orders WHERE id=?", (oid,), one=True)
    if not order:
        return error("Không tìm thấy đơn", 404)
    if order["status"] != "pending":
        return error("Chỉ hủy được đơn chưa thanh toán")
    ex("UPDATE cms_orders SET status='cancelled' WHERE id=?", (oid,))
    return jsonify(ok=True)


@cms.route("/api/cms/payments")
@authenticate
def payments():
    if not role("S0", "AREA", "OWNER"):
        return error("Không có quyền", 403)
    rows = [dict(r) for r in q("SELECT p.*, o.account_id, o.poi_id, x.ward_slug, a.username FROM cms_payments p "
                              "JOIN cms_orders o ON o.id=p.order_id JOIN pois x ON x.id=o.poi_id "
                              "JOIN cms_accounts a ON a.id=o.account_id ORDER BY p.id DESC")]
    if role("OWNER"):
        rows = [r for r in rows if r["account_id"] == g.cms_user["id"]]
    else:
        rows = [r for r in rows if in_scope(r["ward_slug"])]
    return jsonify(items=rows)


def seed_plans():
    if not q("SELECT 1 FROM cms_plans LIMIT 1", one=True):
        t = now()
        for name, price, days in (("Gói 1 tháng", 99000, 30), ("Gói 3 tháng", 249000, 90), ("Gói 12 tháng", 899000, 365)):
            ex("INSERT INTO cms_plans(name,price,duration_days,description,created_at) VALUES(?,?,?,?,?)",
               (name, price, days, "Gói demo cho một ghim", t))
