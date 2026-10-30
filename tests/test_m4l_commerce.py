"""M4L 2.0 Phase 3/4: partner campaigns, mood sponsorship, VIP random pool, Pioneer vouchers, kiosk O2O, analytics."""
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="m4l-com-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "m4l.db"),
    "XANH24_SECRET": "m4l-commerce-test-secret-not-for-production", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
    "XANH24_M4L_ENABLED": "1",
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
    from app import create_app
    import m4l
    import m4l_migrations
    from db import ex, now, q, set_setting

    app = create_app()
    client = app.test_client()
    set_setting("m4l_config", {"random_cooldown_s": 0, "unlock_min_interval_s": 0})

    def cms_login(username, password, section):
        response = client.post("/api/cms/login", json={"username": username, "password": password, "section": section})
        assert response.status_code == 200, response.json
        return {"Authorization": "Bearer " + response.json["token"]}

    def register(username):
        r = client.post("/api/cms/register", json={"username": username, "password": "User@20261", "full_name": f"Người {username}",
                                                     "birth_date": "2000-01-01", "gender": "undisclosed", "email": f"{username}@example.com",
                                                     "phone": "0912345678"})
        assert r.status_code == 201, r.json
        return {"Authorization": "Bearer " + r.json["token"]}, r.json["user"]["id"]

    # ---- schema
    check(q("SELECT MAX(version) v FROM m4l_migrations", one=True)["v"] == 4 == m4l_migrations.LATEST, "migration v4 (thương mại) đã áp dụng")
    for table in ("m4l_campaigns", "m4l_voucher_templates", "m4l_vouchers", "m4l_kiosk_keys", "m4l_kiosk_sessions", "m4l_events"):
        check(q("SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name=?", (table,), one=True)["n"] == 1, f"có bảng {table}")

    # ---- actors: S0, area manager (Hoàn Kiếm), area manager elsewhere, content, partners (OWNER), users
    admin = cms_login("admin", "Admin@2026x", "admin")
    category = q("SELECT id FROM categories ORDER BY id LIMIT 1", one=True)["id"]
    for body in ({"role": "AREA", "username": "qlhk", "password": "Area@2026x", "wards": ["hoan-kiem"]},
                 {"role": "AREA", "username": "qlcg", "password": "Area@2026x", "wards": ["cau-giay"]},
                 {"role": "CONTENT", "username": "ndhk", "password": "Content@2026", "wards": ["hoan-kiem"]}):
        assert client.post("/api/cms/accounts", headers=admin, json=body).status_code == 200
    manager = cms_login("qlhk", "Area@2026x", "manager")
    manager_other = cms_login("qlcg", "Area@2026x", "manager")
    content = cms_login("ndhk", "Content@2026", "admin")

    def partner(username, name, lat, lng):
        r = client.post("/api/cms/accounts", headers=manager, json={"role": "OWNER", "username": username, "password": "Owner@2026x",
                                                                     "full_name": name, "pin": {"name": name, "lat": lat, "lng": lng, "category": category}})
        assert r.status_code == 200, r.json
        pid = r.json["pin_id"]
        ex("UPDATE cms_pins SET approved_at=?, expires_at=? WHERE poi_id=?", (now() - 60, now() + 90 * 86400, pid))  # paid listing
        return cms_login(username, "Owner@2026x", "kiosk"), pid, r.json["id"]

    pa, poi_a, acc_a = partner("doitaca", "[TEST] Quán A", 21.0299, 105.8510)
    pb, poi_b, acc_b = partner("doitacb", "[TEST] Quán B", 21.0305, 105.8520)
    pc, poi_c, acc_c = partner("doitacc", "[TEST] Quán C", 21.0290, 105.8525)
    alice, alice_id = register("alice")
    bob, bob_id = register("bobby")
    carol, _ = register("carol")
    moods = {m["slug"]: m for m in client.get("/api/m4l/admin/moods", headers=admin).json["items"]}
    deadline = moods["chay-deadline"]
    for poi in (poi_a, poi_b, poi_c):
        assert client.put(f"/api/m4l/admin/pois/{poi}/moods", headers=content, json={"moods": [{"id": deadline["id"], "reason": "Bàn rộng, ổ cắm"}]}).status_code == 200

    # ---- partner portal and RBAC
    me = client.get("/api/m4l/partner/me", headers=pa)
    check(me.status_code == 200 and me.json["poi"]["id"] == poi_a and me.json["pos_adapter"] == "mock", "đối tác thấy địa điểm của mình, POS đang là mock")
    check(client.get("/api/m4l/partner/me", headers=alice).status_code == 403, "USER không vào được cổng đối tác")
    check(client.get("/api/m4l/partner/me").status_code == 401, "khách chưa đăng nhập bị chặn")
    check(client.get("/api/m4l/admin/campaigns", headers=pa).status_code == 403, "đối tác không vào được trang duyệt")
    check(client.get("/api/m4l/admin/campaigns", headers=content).status_code == 403, "CONTENT không duyệt chiến dịch")
    check(client.get("/api/m4l/admin/campaigns", headers=alice).status_code == 403, "USER không duyệt chiến dịch")

    t = now()
    window = {"starts_at": t - 60, "ends_at": t + 7 * 86400}
    voucher = {"title": "Giảm 20% đồ uống", "benefit": "Giảm 20% cho hóa đơn đồ uống", "issue_cap": 3, "per_user_cap": 1}

    def create(headers, **body):
        payload = {"kind": "mood_sponsor", "name": "Tài trợ deadline", "mood": "chay-deadline", **window, "voucher": voucher} | body
        return client.post("/api/m4l/partner/campaigns", headers=headers, json=payload)

    bad = create(pa, mood=None)
    check(bad.status_code == 400, "tài trợ mood bắt buộc chọn mood")
    check(create(pa, ends_at=t - 120).status_code == 400, "kết thúc trước bắt đầu bị từ chối")
    check(create(pa, voucher={"title": "x", "benefit": "y"}).status_code == 400, "voucher bắt buộc có hạn mức phát hành")
    r = create(pa, radius_m=3000, exclusive=True, priority=50, package="Gói thử nghiệm", poi_id=poi_b)
    check(r.status_code == 201 and r.json["status"] == "draft" and r.json["poi_id"] == poi_a, "tạo nháp; đối tác không gắn được POI của người khác")
    camp_a = r.json["id"]
    check(r.json["voucher"]["ttl_minutes"] == 60, "voucher mặc định đếm ngược 60 phút (cấu hình)")
    check(client.put(f"/api/m4l/partner/campaigns/{camp_a}", headers=pb, json={"name": "chiếm"}).status_code == 404, "đối tác khác không sửa được chiến dịch")

    discovery = lambda **params: client.get("/api/m4l/discovery", query_string={"mood": "chay-deadline", **params})
    check(discovery().json["sponsored"] is None, "nháp chưa được hiển thị")
    check(client.post(f"/api/m4l/admin/campaigns/{camp_a}/review", headers=manager, json={"action": "approve"}).status_code == 409, "chưa gửi duyệt thì không duyệt được")
    check(client.post(f"/api/m4l/partner/campaigns/{camp_a}/submit", headers=pa).json["status"] == "pending", "đối tác gửi duyệt")
    check(client.put(f"/api/m4l/partner/campaigns/{camp_a}", headers=pa, json={"name": "đổi"}).status_code == 409, "đang chờ duyệt thì không sửa được")
    check(client.post(f"/api/m4l/admin/campaigns/{camp_a}/review", headers=manager_other, json={"action": "approve"}).status_code == 404, "quản lý phường khác không duyệt được")
    check(client.post(f"/api/m4l/admin/campaigns/{camp_a}/review", headers=manager, json={"action": "reject"}).status_code == 400, "từ chối phải ghi lý do")
    check(client.post(f"/api/m4l/admin/campaigns/{camp_a}/review", headers=manager, json={"action": "approve", "note": "OK"}).json["status"] == "approved", "quản lý khu vực duyệt")
    check(q("SELECT 1 FROM audit WHERE action='m4l.campaign.review' AND entity_id=?", (str(camp_a),), one=True), "duyệt được ghi audit")

    # ---- sponsored slot: labelled, geo-scoped, organic list untouched
    near = {"lat": "21.030", "lng": "105.852"}
    result = discovery(**near).json
    organic = discovery(**near, q="Quán").json["items"]
    check(result["sponsored"] and result["sponsored"]["id"] == poi_a and result["sponsored"]["sponsor_label"] == "Tài trợ", "tài trợ hiện ở ô riêng có nhãn")
    check([i["id"] for i in result["items"]] == sorted([i["id"] for i in result["items"]], key=lambda pid: [i["id"] for i in result["items"]].index(pid))
          and all(not i["sponsored"] for i in result["items"]) and len(result["items"]) == 3, "danh sách tự nhiên giữ nguyên, không bị gắn nhãn tài trợ")
    check(discovery(lat="21.20", lng="105.80").json["sponsored"] is None, "ngoài bán kính 3 km không thấy tài trợ")
    check(discovery().json["sponsored"] is None, "không có vị trí thì chiến dịch giới hạn bán kính không hiển thị")
    check(organic and all(not i["sponsored"] for i in organic), "tìm theo từ khóa không chèn tài trợ")
    offer_items = [i for i in result["items"] if i["offer"]]
    check(result["sponsored"]["offer"] and result["sponsored"]["offer"]["campaign_id"] == camp_a and len(offer_items) == 1, "gợi ý có kèm voucher của đối tác")

    # ---- exclusivity
    r = create(pb, radius_m=2000, priority=90)
    camp_b = r.json["id"]
    client.post(f"/api/m4l/partner/campaigns/{camp_b}/submit", headers=pb)
    clash = client.post(f"/api/m4l/admin/campaigns/{camp_b}/review", headers=admin, json={"action": "approve"})
    check(clash.status_code == 409 and clash.json["code"] == "EXCLUSIVE_CONFLICT", "hai đối tác cùng mood, cùng vùng: chặn vì độc quyền")
    check(client.post(f"/api/m4l/admin/campaigns/{camp_b}/review", headers=admin, json={"action": "reject", "note": "Trùng độc quyền"}).json["status"] == "rejected",
          "admin từ chối kèm lý do")
    r = client.put(f"/api/m4l/partner/campaigns/{camp_b}", headers=pb, json={"kind": "vip_spin", "mood": "", "radius_m": None, "priority": 80})
    check(r.status_code == 200 and r.json["status"] == "draft" and r.json["kind"] == "vip_spin", "sửa chiến dịch bị từ chối → về nháp")

    # ---- mood mismatch
    ex("DELETE FROM m4l_poi_moods WHERE poi_id=?", (poi_c,))
    r = create(pc, priority=10)
    camp_c_mood = r.json["id"]
    client.post(f"/api/m4l/partner/campaigns/{camp_c_mood}/submit", headers=pc)
    mismatch = client.post(f"/api/m4l/admin/campaigns/{camp_c_mood}/review", headers=admin, json={"action": "approve"})
    check(mismatch.status_code == 409 and mismatch.json["code"] == "MOOD_MISMATCH", "POI chưa được duyệt gắn mood thì không mua được mood đó")

    # ---- VIP random pool
    client.post(f"/api/m4l/partner/campaigns/{camp_b}/submit", headers=pb)
    check(client.post(f"/api/m4l/admin/campaigns/{camp_b}/review", headers=admin, json={"action": "approve"}).json["status"] == "approved", "duyệt chiến dịch VIP")
    r = client.post("/api/m4l/partner/campaigns", headers=pc, json={"kind": "vip_spin", "name": "VIP hạng thấp", "priority": 20, **window})
    camp_c = r.json["id"]
    client.post(f"/api/m4l/partner/campaigns/{camp_c}/submit", headers=pc)
    client.post(f"/api/m4l/admin/campaigns/{camp_c}/review", headers=admin, json={"action": "approve"})
    picks = [client.post("/api/m4l/discovery/random", headers=alice, json={}).json for _ in range(4)]
    check(all(p["item"]["id"] == poi_b and p["item"]["sponsored"] and p["mode"] == "vip" for p in picks), "random chỉ quay trong nhóm VIP trả phí cao nhất, có nhãn tài trợ")
    check("đối tác VIP" in picks[0]["reason"] and picks[-1]["remaining"] == 6, "lý do minh bạch; lượt còn lại tính ở server")
    check(q("SELECT COUNT(*) n FROM m4l_discovery_events WHERE account_id=? AND sponsored=1 AND campaign_id=?", (alice_id, camp_b), one=True)["n"] == 4,
          "lịch sử random ghi chiến dịch VIP")
    client.post(f"/api/m4l/admin/campaigns/{camp_b}/review", headers=admin, json={"action": "pause"})
    check(client.post("/api/m4l/discovery/random", headers=bob, json={}).json["item"]["id"] == poi_c, "tạm dừng VIP hạng cao → hạng kế tiếp vào pool")
    client.post(f"/api/m4l/admin/campaigns/{camp_c}/review", headers=admin, json={"action": "end"})
    fallback = client.post("/api/m4l/discovery/random", headers=bob, json={}).json
    check(fallback["mode"] == "organic" and not fallback["item"]["sponsored"] and "không tài trợ" in fallback["reason"], "hết VIP: rơi về gợi ý tự nhiên, ghi rõ không tài trợ")
    set_setting("m4l_config", {"random_cooldown_s": 0, "random_vip_fallback": "none"})
    before = q("SELECT COUNT(*) n FROM m4l_discovery_events WHERE account_id=?", (bob_id,), one=True)["n"]
    empty = client.post("/api/m4l/discovery/random", headers=bob, json={}).json
    check(empty["item"] is None and empty["code"] == "NO_VIP_PARTNER"
          and q("SELECT COUNT(*) n FROM m4l_discovery_events WHERE account_id=?", (bob_id,), one=True)["n"] == before, "chính sách 'none': báo trống, không trừ lượt")
    set_setting("m4l_config", {"random_cooldown_s": 0})
    client.post(f"/api/m4l/admin/campaigns/{camp_b}/review", headers=admin, json={"action": "resume"})

    # ---- vouchers: claim, countdown, caps, idempotency, concurrency
    claim = lambda headers, cid=camp_a, **extra: client.post("/api/m4l/vouchers/claim", headers=headers, json={"campaign_id": cid, "source": "discovery", **extra})
    check(claim({}).status_code == 401, "nhận voucher cần đăng nhập")
    check(claim(pa).status_code == 403, "tài khoản đối tác không nhận voucher")
    r = claim(alice, idempotency_key="alice-tap-0001")
    v = r.json["voucher"]
    check(r.status_code == 201 and v["status"] == "issued" and 3590 <= v["seconds_left"] <= 3600 and v["expires_at"] - v["issued_at"] == 3600,
          "voucher gắn tài khoản, hết hạn sau 60 phút theo giờ server")
    check(len(v["code"]) >= 20, "mã QR ngẫu nhiên, đủ dài để không đoán được")
    again = claim(alice, idempotency_key="alice-tap-0001")
    check(again.status_code == 200 and again.json["replayed"] and again.json["voucher"]["id"] == v["id"], "bấm lại cùng mã chống trùng không phát hành thêm")
    check(claim(alice).json["code"] == "ALREADY_CLAIMED", "mỗi người tối đa 1 voucher/chiến dịch")
    wallet = client.get("/api/m4l/vouchers", headers=alice).json
    check(wallet["items"][0]["id"] == v["id"] and abs(wallet["server_time"] - now()) <= 1, "ví voucher trả giờ server để đếm ngược")
    check(client.get(f"/api/m4l/vouchers/{v['id']}", headers=bob).status_code == 404, "không xem được voucher của người khác")
    home = client.get("/api/m4l/home", headers=alice).json
    check(home["vouchers"]["active"] == 1 and home["vouchers"]["next"]["id"] == v["id"], "trang chủ hiện voucher đang chạy")

    racers = [register(f"racer{i}") for i in range(6)]
    results = []

    def grab(headers):
        with app.test_client() as own:
            results.append(own.post("/api/m4l/vouchers/claim", headers=headers, json={"campaign_id": camp_a, "source": "discovery"}).status_code)

    threads = [threading.Thread(target=grab, args=(h,)) for h, _ in racers]
    [th.start() for th in threads]
    [th.join() for th in threads]
    issued = q("SELECT issued_count FROM m4l_voucher_templates WHERE campaign_id=?", (camp_a,), one=True)["issued_count"]
    check(results.count(201) == 2 and issued == 3 and q("SELECT COUNT(*) n FROM m4l_vouchers WHERE campaign_id=?", (camp_a,), one=True)["n"] == 3,
          "6 người nhận đồng thời, hạn mức 3: phát đúng 3 voucher")
    check(claim(carol).json["code"] == "SOLD_OUT", "hết hạn mức → báo hết voucher")
    check(discovery(**near).json["sponsored"]["offer"] is None, "hết voucher thì gợi ý không còn kèm ưu đãi")

    # ---- redeem
    check(client.post("/api/m4l/partner/vouchers/redeem", headers=alice, json={"code": v["code"]}).status_code == 403, "người dùng không tự xác nhận voucher")
    check(client.post("/api/m4l/partner/vouchers/redeem", headers=pb, json={"code": v["code"]}).status_code == 404, "cửa hàng khác không xác nhận được")
    check(client.post("/api/m4l/partner/vouchers/check", headers=pa, json={"code": v["code"]}).json["status"] == "issued", "đối tác kiểm tra trạng thái trước khi đổi")
    codes = []

    def redeem_once(code):
        with app.test_client() as own:
            codes.append(own.post("/api/m4l/partner/vouchers/redeem", headers=pa, json={"code": code}).status_code)

    threads = [threading.Thread(target=redeem_once, args=(v["code"],)) for _ in range(4)]
    [th.start() for th in threads]
    [th.join() for th in threads]
    check(sorted(codes) == [200, 409, 409, 409], "4 lần quét đồng thời: chỉ 1 lần đổi thành công")
    row = q("SELECT * FROM m4l_vouchers WHERE id=?", (v["id"],), one=True)
    check(row["status"] == "redeemed" and row["redeem_ref"].startswith("MOCK-") and row["redeemed_by"] == "doitaca", "ghi người xác nhận và mã POS (mock)")
    again = client.post("/api/m4l/partner/vouchers/redeem", headers=pa, json={"code": v["code"]})
    check(again.status_code == 409 and again.json["code"] == "ALREADY_REDEEMED", "không đổi một voucher hai lần")
    check(q("SELECT 1 FROM audit WHERE action='m4l.voucher.redeem' AND entity_id=?", (str(v["id"]),), one=True), "đổi voucher được ghi audit")
    late = q("SELECT * FROM m4l_vouchers WHERE campaign_id=? AND status='issued' ORDER BY id LIMIT 1", (camp_a,), one=True)
    ex("UPDATE m4l_vouchers SET expires_at=? WHERE id=?", (now() - 1, late["id"]))
    expired = client.post("/api/m4l/partner/vouchers/redeem", headers=pa, json={"code": late["code"]})
    check(expired.status_code == 410 and expired.json["code"] == "EXPIRED", "QR hết hạn bị từ chối")
    owner_wallet = [x for x in client.get("/api/m4l/vouchers", headers=dict(racers[0][0])).json["items"]] + \
                   [x for h, _ in racers for x in client.get("/api/m4l/vouchers", headers=h).json["items"] if x["id"] == late["id"]]
    expired_view = next(x for x in owner_wallet if x["id"] == late["id"])
    check(expired_view["status"] == "expired" and "code" not in expired_view and expired_view["seconds_left"] == 0, "voucher hết hạn: ví ẩn mã QR")
    check(client.post("/api/m4l/partner/vouchers/redeem", headers=admin, json={"code": "khong-ton-tai-123"}).status_code == 404, "mã không tồn tại → 404")

    # ---- campaign guards: expired, partner locked, POI hidden, impression cap
    ex("UPDATE m4l_campaigns SET ends_at=? WHERE id=?", (now() - 1, camp_a))
    check(discovery(**near).json["sponsored"] is None, "chiến dịch hết hạn không còn hiển thị")
    ex("UPDATE m4l_campaigns SET ends_at=? WHERE id=?", (now() + 86400, camp_a))
    ex("UPDATE cms_accounts SET active=0 WHERE id=?", (acc_a,))
    check(discovery(**near).json["sponsored"] is None, "đối tác bị khóa không còn hiển thị")
    ex("UPDATE cms_accounts SET active=1 WHERE id=?", (acc_a,))
    ex("UPDATE pois SET status='hidden' WHERE id=?", (poi_a,))
    check(discovery(**near).json["sponsored"] is None, "địa điểm ngừng hoạt động không còn hiển thị")
    ex("UPDATE pois SET status='published' WHERE id=?", (poi_a,))
    seen = q("SELECT COUNT(*) n FROM m4l_events WHERE type='impression' AND campaign_id=?", (camp_a,), one=True)["n"]
    ex("UPDATE m4l_campaigns SET impression_cap=? WHERE id=?", (seen, camp_a))
    check(discovery(**near).json["sponsored"] is None, "hết hạn mức hiển thị theo hợp đồng thì dừng")
    ex("UPDATE m4l_campaigns SET impression_cap=NULL WHERE id=?", (camp_a,))
    n1 = q("SELECT COUNT(*) n FROM m4l_events WHERE type='impression' AND campaign_id=?", (camp_a,), one=True)["n"]
    fresh_viewer, _ = register("dave")
    client.get("/api/m4l/discovery", headers=fresh_viewer, query_string={"mood": "chay-deadline", **near})
    client.get("/api/m4l/discovery", headers=fresh_viewer, query_string={"mood": "chay-deadline", **near})
    check(q("SELECT COUNT(*) n FROM m4l_events WHERE type='impression' AND campaign_id=?", (camp_a,), one=True)["n"] == n1 + 1, "tải lại trang không thổi phồng lượt hiển thị")

    # ---- kiosk O2O
    ex("INSERT INTO devices(code,name,ward_slug,address,lat,lng,active,created_at) VALUES('KTEST1','[TEST] Trạm Hoàn Kiếm','hoan-kiem','Hoàn Kiếm',21.0295,105.8500,1,?)", (now(),))
    ex("INSERT INTO devices(code,name,ward_slug,lat,lng,active,created_at) VALUES('KTEST2','[TEST] Trạm Cầu Giấy','cau-giay',21.0335,105.7945,1,?)", (now(),))
    kiosk_id = q("SELECT id FROM devices WHERE code='KTEST1'", one=True)["id"]
    other_kiosk = q("SELECT id FROM devices WHERE code='KTEST2'", one=True)["id"]
    check(client.post(f"/api/m4l/admin/kiosks/{other_kiosk}/key", headers=manager).status_code == 404, "quản lý không cấp khóa kiosk ngoài phường")
    r = client.post(f"/api/m4l/admin/kiosks/{kiosk_id}/key", headers=manager)
    key = r.json["key"]
    check(r.status_code == 201 and key.startswith("x24k_") and q("SELECT key_hash FROM m4l_kiosk_keys WHERE device_id=?", (kiosk_id,), one=True)["key_hash"] != key,
          "cấp khóa kiosk, chỉ lưu hash")
    ticket = lambda k=key, **body: client.post("/api/m4l/kiosk/ticket", headers={"X-Kiosk-Key": k}, json={"device": "KTEST1", **body})
    check(ticket("x24k_sai").status_code == 401 and client.post("/api/m4l/kiosk/ticket", json={"device": "KTEST1"}).status_code == 401, "sai/thiếu khóa kiosk bị chặn")
    tk = ticket().json
    check(tk["path"].startswith("/m4l/k/") and tk["expires_at"] - now() <= 180, "kiosk nhận mã check-in ngắn hạn")
    check(ticket(current=tk["token"]).json["token"] == tk["token"], "mã chưa dùng được hiển thị lại, không sinh mới liên tục")
    check(client.get(tk["path"]).status_code == 200, "trang check-in /m4l/k/<mã> mở được")

    k_a = client.post("/api/m4l/partner/campaigns", headers=pa, json={"kind": "kiosk_o2o", "name": "Ghé quán từ trạm", **window,
                                                                      "voucher": {"title": "Tặng trà đá", "benefit": "Tặng 1 trà đá", "issue_cap": 10}}).json["id"]
    k_b = client.post("/api/m4l/partner/campaigns", headers=pb, json={"kind": "kiosk_o2o", "name": "Quán xa trạm", **window,
                                                                      "voucher": {"title": "Giảm 10%", "benefit": "Giảm 10%", "issue_cap": 10}}).json["id"]
    for cid, headers in ((k_a, pa), (k_b, pb)):
        client.post(f"/api/m4l/partner/campaigns/{cid}/submit", headers=headers)
        client.post(f"/api/m4l/admin/campaigns/{cid}/review", headers=manager, json={"action": "approve"})
    check(claim(bob, k_a).json["code"] == "KIOSK_REQUIRED", "voucher kiosk chỉ nhận qua check-in tại trạm")
    check(client.post("/api/m4l/kiosk/checkin", headers=bob, json={"ticket": "gia-mao-0000000000000000"}).status_code == 404, "mã giả mạo bị từ chối")
    ci = client.post("/api/m4l/kiosk/checkin", headers=bob, json={"ticket": tk["token"]})
    offers = ci.json["offers"]
    check(ci.status_code == 200 and [o["campaign_id"] for o in offers] == [k_a] and offers[0]["distance_m"] <= 200, "chỉ gợi ý đối tác trong bán kính trạm")
    check(client.post("/api/m4l/kiosk/checkin", headers=carol, json={"ticket": tk["token"]}).json["code"] == "TICKET_USED", "mã đã quét không dùng lại được")
    check(client.post("/api/m4l/kiosk/checkin", headers=bob, json={"ticket": tk["token"]}).status_code == 200, "cùng người mở lại không lỗi")
    check(ticket(current=tk["token"]).json["token"] != tk["token"], "mã đã dùng → kiosk nhận mã mới")
    r = claim(bob, k_a, source="kiosk", kiosk_session_id=ci.json["session_id"])
    kv = r.json["voucher"]
    check(r.status_code == 201 and kv["source"] == "kiosk"
          and q("SELECT kiosk_session_id FROM m4l_vouchers WHERE id=?", (kv["id"],), one=True)["kiosk_session_id"] == ci.json["session_id"], "voucher kiosk ghi nhận trạm phát hành")
    check(claim(carol, k_a, source="kiosk", kiosk_session_id=ci.json["session_id"]).status_code == 403, "không mượn phiên check-in của người khác")
    expired_tk = ticket().json
    ex("UPDATE m4l_kiosk_sessions SET expires_at=? WHERE used_at IS NULL", (now() - 1,))
    check(client.post("/api/m4l/kiosk/checkin", headers=carol, json={"ticket": expired_tk["token"]}).json["code"] == "TICKET_EXPIRED", "mã quá hạn bị từ chối")
    ex("UPDATE devices SET active=0 WHERE id=?", (kiosk_id,))
    check(ticket().status_code == 403, "kiosk tạm ngưng không tạo phiên")
    ex("UPDATE devices SET active=1 WHERE id=?", (kiosk_id,))
    check(client.delete(f"/api/m4l/admin/kiosks/{kiosk_id}/key", headers=manager).status_code == 200 and ticket().status_code == 401, "thu hồi khóa → kiosk bị chặn")
    check(client.post("/api/m4l/partner/vouchers/redeem", headers=pa, json={"code": kv["code"]}).status_code == 200, "đổi voucher kiosk tại cửa hàng")

    # ---- analytics funnel
    ev = {"type": "nav_click", "event_id": "evt-nav-000001", "campaign_id": k_a, "poi_id": poi_a, "source": "kiosk"}
    client.post("/api/m4l/events", headers=bob, json=ev)
    client.post("/api/m4l/events", headers=bob, json=ev)
    check(client.post("/api/m4l/events", json={"type": "redeem", "event_id": "evt-fake-00001"}).status_code == 400, "client không tự ghi được lượt đổi")
    stats = client.get("/api/m4l/admin/analytics", headers=admin).json
    row = next(c for c in stats["campaigns"] if c["id"] == k_a)
    check(row["impression"] >= 1 and row["claim"] == 1 and row["nav_click"] == 1 and row["redeem"] == 1, "phễu: hiển thị → nhận → chỉ đường → đổi, không đếm trùng")
    check(stats["totals"]["qr_scan"] == 1 and "không phải số khách" in stats["note"], "chỉ lượt quét hợp lệ được tính; báo cáo ghi rõ không phải foot traffic")
    check("alice" not in str(stats) and "bobby" not in str(stats), "báo cáo không lộ danh tính người dùng")
    scoped = client.get("/api/m4l/admin/analytics", headers=manager_other).json
    check(all(c["id"] not in (camp_a, k_a) for c in scoped["campaigns"]), "quản lý phường khác không xem số liệu Hoàn Kiếm")
    mine = client.get("/api/m4l/partner/me", headers=pa).json
    check(all(c["partner_account_id"] == acc_a for c in mine["campaigns"]) and any(c["stats"]["redeem"] for c in mine["campaigns"]), "đối tác xem báo cáo chiến dịch của mình")

    # ---- pages and flag
    for path in ("/m4l/vouchers", "/m4l/partner", "/m4l/station", f"/m4l/v/{kv['code']}"):
        check(client.get(path).status_code == 200, f"trang {path} mở được")
    os.environ["XANH24_M4L_ENABLED"] = "0"
    check(client.get("/api/m4l/vouchers", headers=alice).status_code == 404 and client.post("/api/m4l/kiosk/ticket", json={}).status_code == 404,
          "tắt cờ: API thương mại trả 404")
    check(client.get("/").status_code == 200 and client.get("/dashboard/user").status_code == 200, "tắt cờ: route cũ vẫn chạy")
    os.environ["XANH24_M4L_ENABLED"] = "1"
    for path in ("/", "/dashboard/user", "/cms/login", "/hrm/login", "/admin", "/dashboard/kiosk", "/api/public/pois"):
        check(client.get(path).status_code == 200, f"không regression: {path}")

    print(f"\nM4L thương mại: {passed} kiểm thử đạt")
finally:
    time.sleep(0.2)
    shutil.rmtree(scratch, ignore_errors=True)
