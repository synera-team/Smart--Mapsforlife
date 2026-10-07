"""Xác thực & phân quyền 3 tầng.

S0  — Quản trị cấp cao nhất: toàn quyền (người dùng, cấu hình, module, API, xoá vĩnh viễn).
S1  — Quản trị phê duyệt: duyệt/từ chối, chỉnh sửa trực tiếp, publish, quản lý quảng cáo & thiết bị.
CW  — Co-worker: nhập liệu, import Excel, gửi yêu cầu phê duyệt (không tự publish).
"""
import functools
import hashlib
import json
import os
import secrets
import time

import jwt
from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from db import DATA_DIR, ex, now, q, row2dict

ROLE_LEVEL = {"CW": 1, "S1": 2, "S0": 3}
ROLE_LABEL = {"S0": "Admin S0 — Toàn quyền", "S1": "Admin S1 — Phê duyệt", "CW": "Co-worker — Nhập liệu"}

PERMISSIONS = {
    # permission: minimal role
    "poi.read": "CW", "poi.propose": "CW", "import.run": "CW", "media.upload": "CW",
    "ads.propose": "CW", "stats.read": "CW",
    "poi.approve": "S1", "poi.publish": "S1", "poi.edit_direct": "S1", "ads.publish": "S1",
    "devices.manage": "S1", "transit.manage": "S1", "audit.read": "S1", "wards.edit_info": "S1",
    "users.manage": "S0", "settings.manage": "S0", "modules.manage": "S0", "wards.edit_geometry": "S0",
    "api.manage": "S0", "poi.purge": "S0",
}


def _secret():
    env = os.environ.get("XANH24_SECRET")
    if env:
        return env
    path = os.path.join(DATA_DIR, "secret.key")
    if not os.path.exists(path):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(path, 0o600)
    return open(path).read().strip()


SECRET = None
TOKEN_TTL = 12 * 3600


def secret():
    global SECRET
    if SECRET is None:
        SECRET = _secret()
    return SECRET


def hash_password(p):
    return generate_password_hash(p, method="pbkdf2:sha256:260000")


def check_password(h, p):
    try:
        return check_password_hash(h, p)
    except Exception:
        return False


def password_problem(p):
    if len(p or "") < 8:
        return "Mật khẩu tối thiểu 8 ký tự"
    if p.lower() == p or p.upper() == p or not any(c.isdigit() for c in p):
        return "Mật khẩu cần có chữ hoa, chữ thường và chữ số"
    return None


def issue_token(user):
    payload = {"sub": str(user["id"]), "role": user["role"], "u": user["username"],
               "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, secret(), algorithm="HS256")


def public_user(u):
    d = row2dict(u, ("wards",))
    d.pop("password_hash", None)
    d["role_label"] = ROLE_LABEL.get(d["role"], d["role"])
    d["permissions"] = sorted(p for p, r in PERMISSIONS.items() if ROLE_LEVEL[d["role"]] >= ROLE_LEVEL[r])
    return d


def current_user():
    return getattr(g, "user", None)


def has_perm(user, perm):
    if not user:
        return False
    need = PERMISSIONS.get(perm, "S0")
    return ROLE_LEVEL.get(user["role"], 0) >= ROLE_LEVEL[need]


def ward_allowed(user, ward_slug):
    """CW có thể bị giới hạn trong một số phường; S1/S0 nếu có danh sách cũng bị giới hạn."""
    if not user:
        return False
    try:
        scope = json.loads(user["wards"] or "[]")
    except Exception:
        scope = []
    if not scope or user["role"] == "S0":
        return True
    return ward_slug in scope


def _load_user_from_request():
    hdr = request.headers.get("Authorization", "")
    tok = hdr[7:] if hdr.startswith("Bearer ") else request.cookies.get("x24_token")
    if tok:
        try:
            data = jwt.decode(tok, secret(), algorithms=["HS256"])
            u = q("SELECT * FROM users WHERE id=? AND active=1", (int(data["sub"]),), one=True)
            return u
        except Exception:
            return None
    key = request.headers.get("X-API-Key")
    if key:
        h = hashlib.sha256(key.encode()).hexdigest()
        k = q("SELECT * FROM api_keys WHERE key_hash=? AND active=1", (h,), one=True)
        if k:
            ex("UPDATE api_keys SET last_used=? WHERE id=?", (now(), k["id"]))
            g.api_key = k
            # API key hoạt động như tài khoản chỉ-đọc cấp CW
            return {"id": 0, "username": "api:" + (k["name"] or k["prefix"]), "role": "CW", "wards": "[]", "active": 1}
    return None


def require(perm=None):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            u = _load_user_from_request()
            if not u:
                return jsonify(error="Chưa đăng nhập hoặc phiên đã hết hạn"), 401
            g.user = u
            if perm and not has_perm(u, perm):
                return jsonify(error="Bạn không có quyền thực hiện thao tác này", need=PERMISSIONS.get(perm)), 403
            if getattr(g, "api_key", None) and request.method not in ("GET", "HEAD"):
                return jsonify(error="API key chỉ có quyền đọc"), 403
            return fn(*a, **kw)
        return wrapper
    return deco


def audit(action, entity="", entity_id="", detail=None):
    u = current_user()
    ex("INSERT INTO audit(user_id,username,action,entity,entity_id,detail,ip,at) VALUES(?,?,?,?,?,?,?,?)",
       (u["id"] if u else None, u["username"] if u else "system", action, entity, str(entity_id or ""),
        json.dumps(detail or {}, ensure_ascii=False), request.remote_addr if request else "", now()))


# ---- chống dò mật khẩu đơn giản (theo IP + username) ----
_fails = {}


def login_throttled(key):
    rec = _fails.get(key)
    if not rec:
        return 0
    count, until = rec
    if until and until > time.time():
        return int(until - time.time())
    return 0


def login_failed(key):
    count, until = _fails.get(key, (0, 0))
    count += 1
    until = time.time() + min(900, 30 * (2 ** (count - 5))) if count >= 5 else 0
    _fails[key] = (count, until)


def login_ok(key):
    _fails.pop(key, None)
