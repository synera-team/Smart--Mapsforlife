"""Hosted demo mode (XANH24_DEMO_MODE): one-click sessions, role limits, labelling, rate limit, snapshot/reset, login fixes."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="m4l-demo-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "demo.db"),
    "XANH24_SECRET": "m4l-demo-test-secret-not-for-production", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
    "XANH24_M4L_ENABLED": "1", "XANH24_DEMO_MODE": "1",
})
sys.path.insert(0, str(ROOT / "server"))
sys.stdout.reconfigure(encoding="utf-8")
passed = 0


def check(condition, message):
    global passed
    if not condition:
        raise AssertionError(message)
    passed += 1
    print("  ✓", message)


try:
    import seed_m4l_demo
    check(seed_m4l_demo.main() == 0, "seed demo vào CSDL riêng")
    from app import create_app
    import m4l_demo
    from db import get_setting, now, q, set_setting

    app = create_app()
    client = app.test_client()
    set_setting("m4l_config", {"random_cooldown_s": 0})
    check(m4l_demo.main(["m4l_demo.py", "snapshot"]) == 0 and (scratch / "demo-template.db").exists(), "lưu bản gốc demo (snapshot)")

    def session(role, ip="10.0.0.1", **extra):
        return client.post("/api/m4l/demo/session", json={"role": role, **extra}, environ_base={"REMOTE_ADDR": ip})

    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    # ---- pages
    landing = client.get("/demo")
    check(landing.status_code == 200 and "Trải nghiệm" in landing.get_data(as_text=True) and landing.headers.get("X-Robots-Tag") == "noindex",
          "/demo mở trang giới thiệu (noindex)")
    check(client.get("/api/m4l/demo/info").json["label"] == "[DEMO] – Dữ liệu minh họa", "nhãn [DEMO] – Dữ liệu minh họa")
    check(client.get("/api/m4l/home").json["features"]["demo"] is True, "trang chủ M4L biết đang ở chế độ demo")
    for path in ("/m4l/demo.js", "/m4l/demo-mode.js"):
        check(client.get(path).status_code == 200, f"tải được {path}")

    # ---- user: a fresh throw-away account per visitor
    first, second = session("user", name="  Anh   Hùng "), session("user")
    check(first.status_code == 200 and second.status_code == 200 and first.json["role"] == "USER", "một chạm tạo phiên Người dùng")
    me = client.get("/api/m4l/home", headers=bearer(first.json["token"])).json["user"]
    check(me and me["display_name"] == "Anh Hùng" and me["first_name"] == "Hùng", "tên hiển thị tùy chọn được làm sạch và dùng trong lời chào")
    other = client.get("/api/m4l/home", headers=bearer(second.json["token"])).json["user"]
    check(other["display_name"] == "Khách Demo", "không nhập tên thì dùng “Khách Demo”")
    ids = [r["id"] for r in q("SELECT id FROM cms_accounts WHERE username LIKE 'khach_demo_%'")]
    check(len(ids) == 2, "mỗi lượt nhấn là một tài khoản khách riêng (ví, lượt random, bản đồ riêng)")
    check(client.post("/api/cms/login", json={"username": q("SELECT username FROM cms_accounts WHERE id=?", (ids[0],), one=True)["username"],
                                                "password": "", "section": "user"}).status_code in (400, 401), "tài khoản khách không đăng nhập được bằng mật khẩu")

    spin = client.post("/api/m4l/discovery/random", headers=bearer(first.json["token"]), json={})
    check(spin.status_code == 200 and spin.json["item"]["sponsored"], "khách demo quay hộp mù ra quán VIP [DEMO]")
    offer = spin.json["item"].get("offer")
    check(offer and offer["is_demo"] is True, "ưu đãi mang cờ is_demo để giao diện gắn nhãn")
    claim = client.post("/api/m4l/vouchers/claim", headers=bearer(first.json["token"]),
                        json={"campaign_id": offer["campaign_id"], "source": "random", "idempotency_key": "demo-claim-key-000001"})
    check(claim.status_code in (200, 201) and claim.json["voucher"]["is_demo"], "nhận voucher [DEMO]")
    code = claim.json["voucher"]["code"]

    # ---- partner: the demo partner that owns the voucher, in its own (tab) session
    partner = session("partner", voucher=code)
    check(partner.status_code == 200 and partner.json["role"] == "OWNER", "một chạm mở cổng đối tác của đúng quán phát voucher")
    redeemed = client.post("/api/m4l/partner/vouchers/redeem", headers=bearer(partner.json["token"]), json={"code": code})
    check(redeemed.status_code == 200, "nhân viên quán demo xác nhận voucher")
    check(client.post("/api/m4l/partner/vouchers/redeem", headers=bearer(partner.json["token"]), json={"code": code}).status_code == 409,
          "quét lại voucher đã dùng bị từ chối")
    default_partner = session("partner")
    check(default_partner.status_code == 200 and client.get("/api/m4l/partner/me", headers=bearer(default_partner.json["token"])).status_code == 200,
          "không kèm voucher thì vào cổng đối tác demo mặc định")
    check(session("partner", voucher="khong-ton-tai").status_code == 404, "voucher lạ không mở được phiên đối tác")
    created = client.post("/api/m4l/partner/campaigns", headers=bearer(default_partner.json["token"]),
                          json={"kind": "vip_spin", "name": "Chiến dịch thử của sếp", "priority": 10, "starts_at": now() + 60, "ends_at": now() + 86400,
                                "voucher": {"title": "Ưu đãi thử", "benefit": "Thử", "issue_cap": 5}})
    check(created.status_code == 201 and created.json["is_demo"] == 1, "chiến dịch tạo trên bản demo tự gắn cờ DEMO")

    # ---- manager (AREA) — never the system admin
    manager = session("manager")
    check(manager.status_code == 200 and manager.json["role"] == "AREA", "một chạm mở quản trị khu vực (AREA)")
    check(client.get("/api/m4l/admin/analytics", headers=bearer(manager.json["token"])).status_code == 200, "quản lý demo xem analytics")
    for role in ("admin", "S0", "OWNER", "", None):
        check(session(role).status_code == 400, f"không cấp phiên cho vai trò {role!r}")
    check("m4l_demo_admin" not in str(client.get("/demo").get_data(as_text=True)), "trang demo không lộ tài khoản admin")

    # ---- kiosk: demo key works, and is re-issued if someone rotates it in /m4l/admin
    kiosk = session("kiosk").json["kiosk"]
    ticket = client.post("/api/m4l/kiosk/ticket", json={"device": kiosk["device"]}, headers={"X-Kiosk-Key": kiosk["key"]})
    check(ticket.status_code == 200 and ticket.json["path"].startswith("/m4l/k/"), "trạm demo hiển thị mã check-in")
    device_id = get_setting("m4l_demo_seeded")["device"]
    client.post(f"/api/m4l/admin/kiosks/{device_id}/key", headers=bearer(manager.json["token"]))
    rotated = session("kiosk").json["kiosk"]
    check(rotated["key"] != kiosk["key"] and client.post("/api/m4l/kiosk/ticket", json={"device": rotated["device"]},
                                                         headers={"X-Kiosk-Key": rotated["key"]}).status_code == 200,
          "khóa kiosk bị đổi trong quản trị thì phiên demo tự cấp khóa mới")

    # ---- rate limit per network
    for _ in range(m4l_demo.SESSIONS_PER_IP_HOUR):
        last = session("user", ip="10.9.9.9")
    check(last.status_code == 200 and session("user", ip="10.9.9.9").status_code == 429, "giới hạn số phiên khách mỗi giờ theo mạng")
    check(session("user", ip="10.9.9.8").status_code == 200, "mạng khác không bị ảnh hưởng")

    # ---- login fixes: right password but wrong tab names the right tab
    creds = (scratch / "M4L_DEMO_ACCOUNTS.txt").read_text(encoding="utf-8")
    user_password = next(line for line in creds.splitlines() if "m4l_demo_user" in line).rsplit(" / ", 1)[1].strip()
    wrong_tab = client.post("/api/cms/login", json={"username": "m4l_demo_user", "password": user_password, "section": "kiosk"})
    check(wrong_tab.status_code == 401 and "Người dùng" in wrong_tab.json["error"], "đúng mật khẩu nhưng sai mục: báo đúng mục cần chọn")
    wrong_pw = client.post("/api/cms/login", json={"username": "m4l_demo_user", "password": "sai-mat-khau", "section": "kiosk"})
    check(wrong_pw.status_code == 401 and "Người dùng" not in wrong_pw.json["error"], "sai mật khẩu: không tiết lộ mục của tài khoản")
    check(client.post("/api/cms/login", json={"username": "m4l_demo_user", "password": user_password, "section": "user"}).status_code == 200,
          "đăng nhập Người dùng đúng mục thành công")

    # ---- reset: visitor data gone, seeded demo still live
    check(m4l_demo.main(["m4l_demo.py", "reset"]) == 0, "đặt lại dữ liệu demo")
    check(q("SELECT COUNT(*) n FROM cms_accounts WHERE username LIKE 'khach_demo_%'", one=True)["n"] == 0, "sau reset: không còn tài khoản khách")
    check(q("SELECT COUNT(*) n FROM m4l_vouchers", one=True)["n"] == 0, "sau reset: không còn voucher của khách")
    check(q("SELECT COUNT(*) n FROM m4l_campaigns WHERE is_demo=1 AND status='approved'", one=True)["n"] == 5, "sau reset: 5 chiến dịch demo vẫn chạy")
    again = session("user", ip="10.1.1.1")
    check(again.status_code == 200 and client.post("/api/m4l/discovery/random", headers=bearer(again.json["token"]), json={}).status_code == 200,
          "sau reset: app chạy tiếp không cần khởi động lại")
    check(session("kiosk").json["kiosk"]["key"], "sau reset: trạm demo vẫn có khóa")

    # ---- the CLI refuses anything but a dedicated demo DB
    os.environ["XANH24_DEMO_MODE"] = "0"
    check(m4l_demo.main(["m4l_demo.py", "reset"]) == 2, "CLI từ chối khi không ở chế độ demo")
    check(client.get("/demo").status_code == 404 and session("user").status_code == 404, "tắt cờ demo: /demo và phiên demo trả 404")
    os.environ["XANH24_DEMO_MODE"] = "1"
    print(f"M4L demo: {passed} kiểm thử đạt")
finally:
    try:
        from db import close_all  # noqa: F401
    except ImportError:
        pass
    shutil.rmtree(scratch, ignore_errors=True)
