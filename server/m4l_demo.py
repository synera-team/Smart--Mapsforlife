"""One-click demo sessions for the hosted M4L 2.0 demo (staging only).

Off unless XANH24_DEMO_MODE=1 (and XANH24_M4L_ENABLED=1). Meant for a dedicated demo database built by
seed_m4l_demo.py, never for production: every route here 404s when the flag is off.

  GET  /demo                     landing page with one button per journey
  GET  /api/m4l/demo/info        {enabled: true} so pages can show the "[DEMO]" ribbon and demo login links
  POST /api/m4l/demo/session     {role: user|partner|manager|kiosk, name?, voucher?}

Roles: "user" gets a fresh throw-away USER account per visitor (own wallet, own random quota, own fog);
"partner" and "manager" sign in as the seeded demo OWNER / AREA accounts; "kiosk" returns the demo kiosk key.
The system admin (S0) is never handed out.

CLI (inside the demo container):
  python server/m4l_demo.py snapshot   keep a pristine copy of the freshly seeded DB (demo-template.db)
  python server/m4l_demo.py reset      restore that copy into the live DB and restart the demo clock
"""
import hashlib
import os
import secrets
import sqlite3
import sys

from flask import Blueprint, abort, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auth import hash_password  # noqa: E402
from db import DATA_DIR, DB_PATH, IS_PG, ex, get_setting, now, q, set_setting  # noqa: E402

DEMO_USER_PREFIX = "khach_demo_"
PARTNER_DEFAULT = "m4l_demo_cafe"
MANAGER = "m4l_demo_manager"
SESSIONS_PER_IP_HOUR = 30
MAX_DEMO_USERS = 2000
TEMPLATE = os.path.join(DATA_DIR, "demo-template.db")
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "m4l")

demo = Blueprint("m4l_demo", __name__)


def enabled():
    flag = lambda name: os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")
    return flag("XANH24_DEMO_MODE") and flag("XANH24_M4L_ENABLED")


def _guard():
    if not enabled():
        abort(404)


def _error(message, status=400, code=None):
    return jsonify(error=message, code=code), status


def _ip_hash():
    # Behind Fly.io every request comes from the proxy; Fly-Client-IP is set (and overwritten) by that proxy, so trust it only there.
    ip = request.headers.get("Fly-Client-IP") if os.environ.get("FLY_APP_NAME") else None
    return hashlib.sha256(f"demo|{ip or request.remote_addr}".encode()).hexdigest()[:16]


def _audit(action, account, detail=""):
    ex("INSERT INTO audit(user_id,username,action,entity,entity_id,detail,ip,at) VALUES(?,?,?,?,?,?,?,?)",
       (account["id"], account["username"], action, "demo_session", str(account["id"]), detail, _ip_hash(), now()))


def _staff(username):
    row = q("SELECT * FROM cms_accounts WHERE username=? AND active=1", (username,), one=True)
    if not row or not row["username"].startswith("m4l_demo_"):
        return None
    return row


def _partner_for(code):
    """The demo partner who owns the voucher's campaign, so the 'staff' side of the demo can redeem it."""
    row = q("SELECT a.username FROM m4l_vouchers v JOIN m4l_campaigns c ON c.id=v.campaign_id "
            "JOIN cms_accounts a ON a.id=c.partner_account_id WHERE v.code=? AND c.is_demo=1", (str(code or "")[:64],), one=True)
    return row["username"] if row else None


def _new_user(name):
    display = " ".join(str(name or "").split())[:40] or "Khách Demo"
    username = DEMO_USER_PREFIX + secrets.token_hex(5)
    account_id = ex("INSERT INTO cms_accounts(username,password_hash,full_name,role,created_at) VALUES(?,?,?,'USER',?)",
                    (username, hash_password(secrets.token_urlsafe(24)), display, now()))  # nobody knows this password
    return q("SELECT * FROM cms_accounts WHERE id=?", (account_id,), one=True)


def demo_kiosk():
    """Device code + plaintext key of the demo kiosk; re-issued if someone rotated or revoked it in /m4l/admin."""
    import m4l_commerce as commerce
    seeded = get_setting("m4l_demo_seeded") or {}
    device = q("SELECT id, code FROM devices WHERE id=?", (seeded.get("device"),), one=True) if seeded.get("device") else None
    if not device:
        return None
    saved = get_setting("m4l_demo_kiosk") or {}
    key = saved.get("key")
    try:
        commerce.kiosk_device(device["code"], key)
    except commerce.ServiceError:
        key = commerce.issue_kiosk_key(device["id"], "demo")
        set_setting("m4l_demo_kiosk", {"key": key, "at": now()})
    return {"device": device["code"], "key": key}


@demo.route("/demo")
@demo.route("/demo/")
def landing():
    _guard()
    response = send_from_directory(WEB_DIR, "demo.html")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@demo.route("/api/m4l/demo/info")
def info():
    _guard()
    return jsonify(enabled=True, label="[DEMO] – Dữ liệu minh họa")


@demo.route("/api/m4l/demo/session", methods=["POST"])
def session():
    _guard()
    from cms import token_for
    d = request.get_json(silent=True) or {}
    role = d.get("role")
    if role == "kiosk":
        kiosk = demo_kiosk()
        return jsonify(kiosk=kiosk) if kiosk else _error("Chưa có kiosk demo", 404, "NO_DEMO_KIOSK")
    if role == "user":
        recent = q("SELECT COUNT(*) AS n FROM audit WHERE action='demo_user' AND ip=? AND at>?", (_ip_hash(), now() - 3600), one=True)["n"]
        if recent >= SESSIONS_PER_IP_HOUR:
            return _error("Đã tạo nhiều phiên demo từ mạng này. Thử lại sau ít phút.", 429, "RATE_LIMITED")
        total = q("SELECT COUNT(*) AS n FROM cms_accounts WHERE username LIKE ?", (DEMO_USER_PREFIX + "%",), one=True)["n"]
        if total >= MAX_DEMO_USERS:
            return _error("Bản demo đã đủ lượt khách. Liên hệ Xanh24 để đặt lại dữ liệu demo.", 503, "DEMO_FULL")
        account = _new_user(d.get("name"))
        _audit("demo_user", account)
    elif role in ("partner", "manager"):
        username = MANAGER if role == "manager" else (_partner_for(d.get("voucher")) if d.get("voucher") else PARTNER_DEFAULT)
        account = _staff(username) if username else None
        if not account:
            return _error("Không tìm thấy tài khoản demo cho vai trò này", 404, "NO_DEMO_ACCOUNT")
        _audit(f"demo_{role}", account)
    else:
        return _error("Vai trò demo không hợp lệ", 400, "BAD_ROLE")
    return jsonify(token=token_for(account), role=account["role"], name=account["full_name"])


# ---------------------------------------------------------------- CLI: snapshot / reset
def refresh_clock():
    """Keep demo campaigns and paid listings live for 30/60 more days from now."""
    t = now()
    ex("UPDATE m4l_campaigns SET starts_at=?, ends_at=?, updated_at=? WHERE is_demo=1 AND status='approved'", (t - 60, t + 30 * 86400, t))
    ex("UPDATE cms_pins SET expires_at=? WHERE poi_id IN (SELECT poi_id FROM m4l_campaigns WHERE is_demo=1)", (t + 60 * 86400,))


def _copy(src_path, dst_path):
    src, dst = sqlite3.connect(src_path), sqlite3.connect(dst_path, timeout=30)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def snapshot():
    from app import create_app
    with create_app().app_context():
        if not get_setting("m4l_demo_seeded"):
            print("Chưa seed demo (chạy seed_m4l_demo.py trước).")
            return 2
        demo_kiosk()  # store a usable kiosk key in the template
        refresh_clock()
    _copy(DB_PATH, TEMPLATE)
    print(f"Đã lưu bản gốc demo: {TEMPLATE}")
    return 0


def reset():
    if not os.path.exists(TEMPLATE):
        print(f"Không có bản gốc demo {TEMPLATE} (chạy 'snapshot' sau khi seed).")
        return 2
    _copy(TEMPLATE, DB_PATH)  # SQLite online backup: safe while the server keeps its connections open
    from app import create_app
    with create_app().app_context():
        refresh_clock()
    print("Đã đặt lại dữ liệu demo về bản gốc.")
    return 0


def main(argv):
    if not enabled() or IS_PG or os.path.realpath(DB_PATH) == os.path.realpath(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "xanh24.db")):
        print("Từ chối: chỉ dùng cho CSDL demo riêng (XANH24_DEMO_MODE=1, XANH24_M4L_ENABLED=1, XANH24_DB trỏ tới thư mục demo).")
        return 2
    commands = {"snapshot": snapshot, "reset": reset}
    if len(argv) < 2 or argv[1] not in commands:
        print(__doc__)
        return 1
    return commands[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
