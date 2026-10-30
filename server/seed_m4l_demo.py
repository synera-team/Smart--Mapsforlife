"""Seed a clearly labelled M4L 2.0 demo (moods, places, partners, campaigns, vouchers, kiosk, mystery pins).

    XANH24_M4L_ENABLED=1 XANH24_DATA_DIR=/path/to/demo XANH24_DB=/path/to/demo/xanh24.db python server/seed_m4l_demo.py

Refuses to run against the default data/xanh24.db or Postgres, so demo rows never reach production.
Every place and campaign is named "[DEMO] …" and campaigns carry is_demo=1; none is a real business.
Passwords are random and written only to <data dir>/M4L_DEMO_ACCOUNTS.txt (ignored by Git).
Running it again does nothing once the demo exists.
"""
import os
import secrets
import sys

os.environ.setdefault("XANH24_M4L_ENABLED", "1")

from app import create_app, ward_for  # noqa: E402
from auth import hash_password  # noqa: E402
from db import BASE_DIR, DATA_DIR, DB_PATH, IS_PG, ex, get_setting, now, q, set_setting  # noqa: E402

FILE = os.path.join(DATA_DIR, "M4L_DEMO_ACCOUNTS.txt")
NOTE = "Dữ liệu DEMO để nghiệm thu M4L — không phải đối tác hay ưu đãi thật."

# name, category, lat, lng, moods {slug: reason}, hours
PARTNERS = {
    "cafe": ("[DEMO] Cà phê Trang Sách", "an-uong", 21.0262, 105.8550, {"chay-deadline": "Bàn rộng, ổ cắm, wifi ổn định"}, "07:00–22:30"),
    "bun": ("[DEMO] Quán Bún Đêm Phố Cổ", "an-uong", 21.0335, 105.8500, {"am-thuc-dem": "Mở tới 2 giờ sáng"}, "17:00–02:00"),
    "tra": ("[DEMO] Góc Trà Hồ Tây", "an-uong", 21.0585, 105.8300, {"hen-ho": "Ban công nhìn hồ, nhạc nhẹ", "xa-stress": "Yên tĩnh, nhiều cây xanh"}, "09:00–23:00"),
    "banh": ("[DEMO] Tiệm Bánh Sáng Sớm", "an-uong", 21.0305, 105.8500, {"chay-deadline": "Có góc ngồi làm việc buổi sáng"}, "06:00–20:00"),
    "gym": ("[DEMO] Phòng Tập Thả Lỏng", "du-lich", 21.0330, 105.7990, {"xa-stress": "Yoga và giãn cơ buổi tối"}, "06:00–21:00"),
}
ORGANIC = (
    ("[DEMO] Thư viện mở Góc Phố", "giao-duc", 21.0250, 105.8470, {"chay-deadline": "Không gian đọc yên tĩnh, miễn phí"}, "08:00–21:00"),
    ("[DEMO] Vườn hoa Yên Lặng", "cong-vien", 21.0315, 105.8420, {"xa-stress": "Ghế đá dưới tán cây"}, "Cả ngày"),
    ("[DEMO] Quán chè khuya Hàng Bạc", "an-uong", 21.0345, 105.8530, {"am-thuc-dem": "Chè nóng mở muộn"}, "18:00–01:00"),
    ("[DEMO] Sân thượng ngắm hoàng hôn", "du-lich", 21.0470, 105.8370, {"hen-ho": "Ngắm hoàng hôn trên hồ"}, "16:00–23:00"),
)
KIOSK = ("M4L-DEMO-01", "[DEMO] Trạm Xanh24 Hồ Gươm", 21.0300, 105.8495)
# teaser, reveal title, reveal text, partner key or (lat, lng)
PINS = (
    ("Nơi những trang sách thơm mùi cà phê", "Cà phê Trang Sách", "Bạn đã tìm thấy góc đọc bí mật bên hồ.", "cafe"),
    ("Mùi nước dùng lúc nửa đêm", "Bún đêm phố cổ", "Đi muộn mới gặp được hương vị này.", "bun"),
    ("Hồ nước và một ấm trà", "Góc trà Hồ Tây", "Một chỗ hẹn hò yên tĩnh.", "tra"),
    ("Cây cầu sắt trăm tuổi", "Cầu Long Biên", "Đi bộ trên lối dành cho người đi bộ để ngắm sông Hồng.", (21.0432, 105.8577)),
    ("Công viên giữa phố sách", "Công viên Cầu Giấy", "Một vòng hồ dạo bộ buổi chiều.", (21.0302, 105.7956)),
    ("Phố lụa phía tây nam", "Làng lụa Vạn Phúc", "Ghé làng nghề dệt lụa lâu đời của Hà Đông.", (20.9800, 105.7740)),
)


def password():
    return secrets.token_urlsafe(12) + "Aa1!"


def call(client, method, path, headers=None, payload=None, ok=(200, 201)):
    response = client.open(path, method=method, headers=headers, json=payload)
    if response.status_code not in ok:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.get_json()}")
    return response.get_json()


def main():
    if IS_PG or os.path.realpath(DB_PATH) == os.path.realpath(os.path.join(BASE_DIR, "data", "xanh24.db")):
        print("Từ chối: chỉ seed demo vào CSDL riêng (đặt XANH24_DB và XANH24_DATA_DIR tới thư mục demo).")
        return 2
    app = create_app()
    with app.app_context():
        if get_setting("m4l_demo_seeded"):
            print(f"Demo M4L đã có. Thông tin đăng nhập: {FILE}")
            return 0
        if not q("SELECT 1 FROM m4l_areas WHERE slug='ha-noi'", one=True):
            print("Chưa có khu vực Hà Nội (migration v3). Bật XANH24_M4L_ENABLED=1 rồi chạy lại.")
            return 2
        client = app.test_client()
        creds = {"admin": ("m4l_demo_admin", password()), "manager": ("m4l_demo_manager", password()), "user": ("m4l_demo_user", password())}
        creds.update({f"partner_{key}": (f"m4l_demo_{key}", password()) for key in PARTNERS})
        for username, _ in creds.values():
            if q("SELECT 1 FROM users WHERE username=?", (username,), one=True) or q("SELECT 1 FROM cms_accounts WHERE username=?", (username,), one=True):
                raise RuntimeError(f"Tài khoản {username} đã tồn tại; không ghi đè mật khẩu")

        ex("INSERT INTO users(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)",
           (creds["admin"][0], hash_password(creds["admin"][1]), "M4L Demo Admin", "S0", now()))
        login = lambda key, section: {"Authorization": "Bearer " + call(client, "POST", "/api/cms/login", payload={
            "username": creds[key][0], "password": creds[key][1], "section": section})["token"]}
        admin = login("admin", "admin")
        partner_wards = sorted({ward_for(p[2], p[3]) for p in PARTNERS.values()} | {ward_for(KIOSK[2], KIOSK[3])})
        call(client, "POST", "/api/cms/accounts", admin, {"role": "AREA", "username": creds["manager"][0], "password": creds["manager"][1],
                                                         "full_name": "M4L Demo Manager", "wards": partner_wards})
        manager = login("manager", "manager")

        poi_ids, partner_headers = {}, {}
        for key, (name, category, lat, lng, _, hours) in PARTNERS.items():
            username, secret = creds[f"partner_{key}"]
            result = call(client, "POST", "/api/cms/accounts", manager, {"role": "OWNER", "username": username, "password": secret,
                                                                        "full_name": name, "pin": {"name": name, "lat": lat, "lng": lng, "category": category, "address": "Hà Nội (địa chỉ demo)"}})
            poi_ids[key] = result["pin_id"]
            # Stands in for the paid listing flow (cms_orders/cms_payments): listing approved for the demo period only.
            ex("UPDATE cms_pins SET approved_at=?, expires_at=? WHERE poi_id=?", (now(), now() + 60 * 86400, result["pin_id"]))
            ex("UPDATE pois SET description=?, hours=? WHERE id=?", (NOTE, hours, result["pin_id"]))
            partner_headers[key] = login(f"partner_{key}", "kiosk")
        organic_ids = []
        for name, category, lat, lng, _, hours in ORGANIC:
            organic_ids.append(ex("INSERT INTO pois(name,category,address,lat,lng,ward_slug,description,hours,status,created_at,updated_at) "
                                  "VALUES(?,?,?,?,?,?,?,?,'published',?,?)", (name, category, "Hà Nội (địa chỉ demo)", lat, lng, ward_for(lat, lng), NOTE, hours, now(), now())))

        moods = {m["slug"]: m["id"] for m in call(client, "GET", "/api/m4l/admin/moods", admin)["items"]}
        for poi_id, links in [(poi_ids[k], PARTNERS[k][4]) for k in PARTNERS] + list(zip(organic_ids, [o[4] for o in ORGANIC])):
            call(client, "PUT", f"/api/m4l/admin/pois/{poi_id}/moods", admin, {"moods": [{"id": moods[slug], "reason": reason} for slug, reason in links.items()]})

        t = now()
        window = {"starts_at": t - 60, "ends_at": t + 30 * 86400}
        campaigns = (
            ("cafe", {"kind": "mood_sponsor", "name": "[DEMO] Tài trợ Góc chạy deadline", "mood": "chay-deadline", "radius_m": 3000, "exclusive": True,
                      "priority": 50, "package": "Demo — tài trợ mood", "voucher": {"title": "Giảm 20% đồ uống", "benefit": "Giảm 20% hóa đơn đồ uống (demo)",
                                                                                    "terms": "Áp dụng 1 lần, không cộng dồn. Dữ liệu demo.", "issue_cap": 200}}),
            ("gym", {"kind": "mood_sponsor", "name": "[DEMO] Tài trợ Cần xả stress", "mood": "xa-stress", "radius_m": 3000, "priority": 30,
                     "package": "Demo — tài trợ mood", "voucher": {"title": "Buổi tập thử miễn phí", "benefit": "1 buổi yoga thử (demo)", "issue_cap": 50}}),
            ("bun", {"kind": "vip_spin", "name": "[DEMO] VIP hộp mù — Bún đêm", "priority": 80, "package": "Demo — VIP random",
                     "voucher": {"title": "Tặng trà đá", "benefit": "Tặng 1 cốc trà đá kèm bát bún (demo)", "issue_cap": 300}}),
            ("tra", {"kind": "vip_spin", "name": "[DEMO] VIP hộp mù — Góc trà", "priority": 80, "package": "Demo — VIP random",
                     "voucher": {"title": "Giảm 10% ấm trà đôi", "benefit": "Giảm 10% cho bàn 2 người (demo)", "issue_cap": 100}}),
            ("banh", {"kind": "kiosk_o2o", "name": "[DEMO] Ghé tiệm từ trạm Hồ Gươm", "priority": 10, "package": "Demo — kiosk O2O",
                      "voucher": {"title": "Giảm 10.000đ", "benefit": "Giảm 10.000đ cho đơn từ 40.000đ (demo)", "issue_cap": 300}}),
        )
        campaign_ids = []
        for key, body in campaigns:
            created = call(client, "POST", "/api/m4l/partner/campaigns", partner_headers[key], {**body, **window})
            ex("UPDATE m4l_campaigns SET is_demo=1 WHERE id=?", (created["id"],))
            call(client, "POST", f"/api/m4l/partner/campaigns/{created['id']}/submit", partner_headers[key])
            call(client, "POST", f"/api/m4l/admin/campaigns/{created['id']}/review", admin, {"action": "approve", "note": "Duyệt cho môi trường demo"})
            campaign_ids.append(created["id"])

        code, kname, klat, klng = KIOSK
        device = q("SELECT id FROM devices WHERE code=?", (code,), one=True)
        device_id = device["id"] if device else ex("INSERT INTO devices(code,name,ward_slug,address,lat,lng,active,notes,created_at) VALUES(?,?,?,?,?,?,1,?,?)",
                                                  (code, kname, ward_for(klat, klng), "Hồ Gươm (demo)", klat, klng, NOTE, now()))
        kiosk_key = call(client, "POST", f"/api/m4l/admin/kiosks/{device_id}/key", admin)["key"]

        pins, skipped = [], []
        for teaser, title, text, where in PINS:
            body = {"area": "ha-noi", "teaser": teaser, "reveal_title": title, "reveal_text": text, "status": "published"}
            body.update({"poi_id": poi_ids[where]} if isinstance(where, str) else {"lat": where[0], "lng": where[1]})
            response = client.post("/api/m4l/admin/pins", headers=admin, json=body)
            (pins if response.status_code == 201 else skipped).append(title if response.status_code == 201 else f"{title}: {response.get_json().get('error')}")

        user = call(client, "POST", "/api/cms/register", payload={"username": creds["user"][0], "password": creds["user"][1], "full_name": "Người dùng Demo",
                                                                   "birth_date": "2000-01-01", "gender": "undisclosed", "email": "m4l-demo-user@example.invalid",
                                                                   "phone": "0900000000"})
        set_setting("m4l_demo_seeded", {"at": now(), "pois": list(poi_ids.values()) + organic_ids, "campaigns": campaign_ids, "device": device_id,
                                        "user": user["user"]["id"]})

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as out:
        out.write(f"M4L demo — {DB_PATH}\n{NOTE}\n\n")
        out.write(f"Quản trị hệ thống (S0) /hrm/login → Quản trị viên: {creds['admin'][0]} / {creds['admin'][1]}\n")
        out.write(f"Nhân viên quản lí (AREA {', '.join(partner_wards)}) /hrm/login → Nhân viên quản lí: {creds['manager'][0]} / {creds['manager'][1]}\n")
        out.write(f"Người dùng /cms/login → Người dùng: {creds['user'][0]} / {creds['user'][1]}\n")
        for key in PARTNERS:
            out.write(f"Đối tác {PARTNERS[key][0]} /cms/login → Tài khoản kiosk: {creds[f'partner_{key}'][0]} / {creds[f'partner_{key}'][1]}\n")
        out.write(f"\nKiosk {code}: mở /m4l/station, mã kiosk {code}, khóa {kiosk_key}\n")
        out.write(f"Ghim bí ẩn đã tạo: {', '.join(pins) or 'không'}\n")
        if skipped:
            out.write(f"Ghim bỏ qua: {'; '.join(skipped)}\n")
    print(f"Đã tạo demo M4L ({len(poi_ids) + len(organic_ids)} địa điểm, {len(campaign_ids)} chiến dịch, {len(pins)} ghim). Thông tin: {FILE}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
