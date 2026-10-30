"""M4L 2.0 Phase 1: feature flag, migration safety, mood admin permissions, discovery filters, legacy routes."""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="m4l-check-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "m4l.db"),
    "XANH24_SECRET": "m4l-test-secret-not-for-production", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
})
os.environ.pop("XANH24_M4L_ENABLED", None)
sys.path.insert(0, str(ROOT / "server"))
sys.stdout.reconfigure(encoding="utf-8")
passed = 0


def check(condition, message):
    global passed
    if not condition:
        raise AssertionError(message)
    passed += 1
    print("  ✓", message)


def m4l_tables():
    conn = sqlite3.connect(scratch / "m4l.db")
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'm4l_%'")}
    finally:
        conn.close()


try:
    from app import create_app
    import m4l
    import m4l_migrations
    from db import ex, now, q

    client = create_app().test_client()
    LEGACY = ("/", "/dashboard/user", "/admin", "/cms/login", "/hrm/login", "/dashboard/kiosk", "/dashboard/admin")

    # ---- flag off (default)
    check(client.get("/m4l").status_code == 404, "cờ tắt: /m4l trả 404")
    check(client.get("/m4l/discover").status_code == 404, "cờ tắt: /m4l/discover trả 404")
    check(client.get("/m4l/m4l.js").status_code == 404, "cờ tắt: tài nguyên /m4l không phục vụ")
    r = client.get("/api/m4l/moods")
    check(r.status_code == 404 and r.is_json, "cờ tắt: /api/m4l/* trả 404 JSON")
    check(not m4l_tables(), "cờ tắt: không tạo bảng m4l_*")

    # ---- enable: backup + additive migration
    users_before = q("SELECT COUNT(*) n FROM users", one=True)["n"]
    pois_before = q("SELECT COUNT(*) n FROM pois", one=True)["n"]
    os.environ["XANH24_M4L_ENABLED"] = "1"
    check(m4l.init_m4l(log=lambda m: None), "bật cờ: migration thành công")
    check({"m4l_migrations", "m4l_moods", "m4l_poi_moods"} <= m4l_tables(), "tạo đủ bảng Phase 1")
    backups = list((scratch / "backups").glob("m4l-pre-m4l-v*.db"))
    check(len(backups) == 1, "có bản sao lưu SQLite trước migration")
    bk = sqlite3.connect(backups[0])
    check(bk.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and bk.execute("SELECT COUNT(*) FROM pois").fetchone()[0] == pois_before,
          "bản sao lưu toàn vẹn và đủ địa điểm")
    bk.close()
    check(m4l.init_m4l(log=lambda m: None) and q("SELECT COUNT(*) n FROM m4l_migrations", one=True)["n"] == m4l_migrations.LATEST
          and q("SELECT COUNT(*) n FROM m4l_moods", one=True)["n"] == 4, "chạy lại migration không nhân bản dữ liệu")
    check(len(list((scratch / "backups").glob("*.db"))) == 1, "không sao lưu lại khi không có migration mới")
    check(q("SELECT COUNT(*) n FROM users", one=True)["n"] == users_before and q("SELECT COUNT(*) n FROM pois", one=True)["n"] == pois_before,
          "migration giữ nguyên users và pois")
    check(q("SELECT COUNT(*) n FROM m4l_poi_moods", one=True)["n"] == 0, "migration không tự gán mood cho địa điểm")

    # ---- pages & legacy routes with flag on
    page = client.get("/m4l")
    check(page.status_code == 200 and 'id="m4l-app"' in page.get_data(as_text=True), "/m4l hiển thị")
    check(client.get("/m4l/discover").status_code == 200 and client.get("/m4l/admin").status_code == 200, "/m4l/discover và /m4l/admin hiển thị")
    check(client.get("/m4l/m4l.js").status_code == 200 and client.get("/m4l/mood-icons.js").status_code == 200, "tài nguyên M4L phục vụ khi bật cờ")
    check(client.get("/m4l/unknown").status_code == 404 and client.get("/m4l/../server/app.py").status_code == 404, "đường dẫn lạ dưới /m4l bị chặn")
    for path in LEGACY:
        check(client.get(path).status_code == 200, f"không regression: {path}")
    check(client.get("/api/public/pois").status_code == 200, "không regression: /api/public/pois")

    # ---- accounts
    def cms_login(username, password, section):
        response = client.post("/api/cms/login", json={"username": username, "password": password, "section": section})
        assert response.status_code == 200, response.json
        return {"Authorization": "Bearer " + response.json["token"]}

    admin = cms_login("admin", "Admin@2026x", "admin")
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "noidung", "password": "Content@2026", "wards": ["hoan-kiem"]}).status_code == 200
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "AREA", "username": "khuvuc", "password": "Area@2026x", "wards": ["hoan-kiem"]}).status_code == 200
    content = cms_login("noidung", "Content@2026", "admin")
    area = cms_login("khuvuc", "Area@2026x", "manager")
    reg = client.post("/api/cms/register", json={"username": "minhanh", "password": "MinhAnh@2026", "full_name": "Trần Minh Anh",
                                                   "birth_date": "2001-05-06", "gender": "female", "email": "ma@example.com", "phone": "0912345678"})
    assert reg.status_code == 201, reg.json
    user = {"Authorization": "Bearer " + reg.json["token"]}

    # ---- home
    home = client.get("/api/m4l/home").json
    check(home["user"] is None and not home["session_expired"], "khách: không có dữ liệu cá nhân")
    check([m["slug"] for m in home["moods"]] == ["chay-deadline", "xa-stress", "hen-ho", "am-thuc-dem"], "khách thấy mood công khai theo thứ tự")
    check(home["features"] == {"discovery": True, "random": True, "exploration": True, "vouchers": True, "demo": False} and home["progress"] is None,
          "voucher đã bật (Phase 3); chế độ demo tắt mặc định; khách không có tiến độ")
    check(client.get("/demo").status_code == 404 and client.get("/api/m4l/demo/info").status_code == 404
          and client.post("/api/m4l/demo/session", json={"role": "manager"}).status_code == 404, "không bật XANH24_DEMO_MODE thì /demo và phiên demo trả 404")
    home = client.get("/api/m4l/home", headers=user).json
    check(home["user"] == {"display_name": "Trần Minh Anh", "first_name": "Anh"}, "USER: chào đúng tên từ hồ sơ")
    check("email" not in str(home["user"]) and "phone" not in str(home["user"]), "home không lộ email/điện thoại")
    home = client.get("/api/m4l/home", headers={"Authorization": "Bearer not-a-token"}).json
    check(home["user"] is None and home["session_expired"], "token hỏng: coi như khách và báo hết phiên")
    check(client.get("/api/m4l/home", headers=area).json["user"] is None, "vai trò khác USER không được cá nhân hóa")

    # ---- admin permissions
    check(client.get("/api/m4l/admin/moods").status_code == 401, "admin API yêu cầu đăng nhập")
    check(client.get("/api/m4l/admin/moods", headers=user).status_code == 403, "USER không vào admin mood")
    check(client.get("/api/m4l/admin/moods", headers=area).status_code == 403, "AREA không vào admin mood")
    r = client.get("/api/m4l/admin/moods", headers=content)
    check(r.status_code == 200 and r.json["can_edit"] is False, "CONTENT xem được, không sửa được mood")
    check(client.post("/api/m4l/admin/moods", headers=content, json={"slug": "cafe-sach", "name": "Cafe sách"}).status_code == 403, "CONTENT không tạo mood")
    r = client.post("/api/m4l/admin/moods", headers=admin, json={"slug": "cafe-sach", "name": "Cafe sách", "icon": "book", "sort_order": 50})
    check(r.status_code == 201 and r.json["slug"] == "cafe-sach", "S0 tạo mood")
    new_mood = r.json["id"]
    check(client.post("/api/m4l/admin/moods", headers=admin, json={"slug": "cafe-sach", "name": "Trùng"}).json["code"] == "CONFLICT", "slug trùng → 409")
    check(client.post("/api/m4l/admin/moods", headers=admin, json={"slug": "Cafe Sách", "name": "x"}).status_code == 400, "slug sai định dạng → 400")
    check(client.post("/api/m4l/admin/moods", headers=admin, json={"slug": "abc", "name": "x", "icon": "<svg>"}).status_code == 400, "icon ngoài danh sách → 400")
    check(client.post("/api/m4l/admin/moods", headers=admin, json={"slug": "abc", "name": ""}).status_code == 400, "thiếu tên → 400")
    check(client.put(f"/api/m4l/admin/moods/{new_mood}", headers=admin, json={"slug": "doi-slug"}).status_code == 400, "không đổi được slug")
    check(client.put("/api/m4l/admin/moods/99999", headers=admin, json={"name": "x"}).status_code == 404, "sửa mood không tồn tại → 404")

    # ---- POI ↔ mood links
    deadline = q("SELECT id FROM m4l_moods WHERE slug='chay-deadline'", one=True)["id"]
    stress = q("SELECT id FROM m4l_moods WHERE slug='xa-stress'", one=True)["id"]
    hk = [r["id"] for r in q("SELECT id FROM pois WHERE ward_slug='hoan-kiem' AND status='published' ORDER BY id")]
    other = q("SELECT id FROM pois WHERE ward_slug!='hoan-kiem' AND ward_slug IS NOT NULL AND status='published' ORDER BY id LIMIT 1", one=True)["id"]
    assert len(hk) >= 3, hk
    listed = client.get("/api/m4l/admin/pois", headers=content).json
    check(listed["total"] > 0 and all(p["ward_slug"] == "hoan-kiem" for p in listed["items"]), "CONTENT chỉ thấy địa điểm trong phường được giao")
    r = client.put(f"/api/m4l/admin/pois/{hk[0]}/moods", headers=content, json={"moods": [{"id": deadline, "reason": "Yên tĩnh, có chỗ ngồi"}, {"id": stress}]})
    check(r.status_code == 200 and len(r.json["moods"]) == 2, "CONTENT gán mood cho địa điểm trong phường")
    check(client.put(f"/api/m4l/admin/pois/{other}/moods", headers=content, json={"moods": [{"id": deadline}]}).status_code == 403, "CONTENT không gán ngoài phường")
    check(client.put(f"/api/m4l/admin/pois/{other}/moods", headers=user, json={"moods": [{"id": deadline}]}).status_code == 403, "USER không gán mood")
    check(client.put(f"/api/m4l/admin/pois/{hk[1]}/moods", headers=content, json={"moods": [{"id": 99999}]}).status_code == 400, "mood không tồn tại → 400")
    check(client.put(f"/api/m4l/admin/pois/{hk[1]}/moods", headers=content, json={"moods": "x"}).status_code == 400, "payload sai → 400")
    check(client.put("/api/m4l/admin/pois/999999/moods", headers=admin, json={"moods": []}).status_code == 404, "địa điểm không tồn tại → 404")
    for pid in (hk[1], hk[2], other):
        assert client.put(f"/api/m4l/admin/pois/{pid}/moods", headers=admin, json={"moods": [{"id": deadline, "reason": "Có wifi"}]}).status_code == 200
    check(q("SELECT COUNT(*) n FROM audit WHERE action='m4l.poi_moods.set'", one=True)["n"] == 4, "mỗi lần gán mood ghi audit")
    check(q("SELECT COUNT(*) n FROM audit WHERE action='m4l.mood.create'", one=True)["n"] == 1, "tạo mood ghi audit")
    r = client.put(f"/api/m4l/admin/pois/{hk[2]}/moods", headers=admin, json={"moods": []})
    check(r.status_code == 200 and not q("SELECT 1 FROM m4l_poi_moods WHERE poi_id=?", (hk[2],), one=True), "gỡ hết mood khỏi địa điểm")

    # ---- discovery filters
    expected = {hk[0], hk[1], other}
    d = client.get("/api/m4l/discovery?mood=chay-deadline").json
    check({i["id"] for i in d["items"]} == expected and d["total"] == 3, "mood Deadline trả đúng địa điểm đã gán")
    check(all(i["sponsored"] is False for i in d["items"]) and d["mood"]["slug"] == "chay-deadline", "kết quả organic, không gắn tài trợ")
    first = next(i for i in d["items"] if i["id"] == hk[0])
    check(first["reasons"] == ["Yên tĩnh, có chỗ ngồi"] and set(first["moods"]) == {"chay-deadline", "xa-stress"}, "trả lý do phù hợp của mood đang chọn")
    check(client.get("/api/m4l/discovery?mood=chay-deadline").json["items"] == d["items"], "thứ tự kết quả xác định")
    counts = {m["slug"]: m["poi_count"] for m in client.get("/api/m4l/moods").json["items"]}
    check(counts["chay-deadline"] == 3 and counts["xa-stress"] == 1 and counts["hen-ho"] == 0, "số địa điểm theo mood lấy từ DB")
    check(client.get("/api/m4l/discovery?mood=hen-ho").json["items"] == [], "mood chưa gán địa điểm → danh sách trống")
    check(client.get("/api/m4l/discovery?mood=khong-co").json["code"] == "MOOD_NOT_FOUND", "mood không tồn tại → 404")

    lake = (21.0287, 105.8524)
    d = client.get(f"/api/m4l/discovery?mood=chay-deadline&lat={lake[0]}&lng={lake[1]}").json
    distances = [i["distance_m"] for i in d["items"]]
    check(d["sort"] == "distance" and distances == sorted(distances), "có vị trí: xếp gần nhất trước")
    near = client.get(f"/api/m4l/discovery?mood=chay-deadline&lat={lake[0]}&lng={lake[1]}&radius=1500").json
    check(all(i["distance_m"] <= 1500 for i in near["items"]) and near["total"] < 3, "lọc theo bán kính")
    a = client.get("/api/m4l/discovery?limit=2").json
    b = client.get(f"/api/m4l/discovery?limit=2&cursor={a['next_cursor']}").json
    full = client.get("/api/m4l/discovery?limit=4").json
    check(a["next_cursor"] == 2 and [i["id"] for i in a["items"] + b["items"]] == [i["id"] for i in full["items"]], "phân trang theo cursor không trùng/sót")
    check(any("Hoàn Kiếm" in i["name"] for i in client.get("/api/m4l/discovery?q=ho%20guom").json["items"]), "tìm không dấu: “ho guom”")
    cat = client.get("/api/m4l/discovery?category=di-tich").json["items"]
    check(cat and all(i["category"] == "di-tich" for i in cat), "lọc theo loại địa điểm")
    for bad, code in (("mood=Bad%20Slug!", "INVALID_PARAMETER"), ("lat=21", "INVALID_LOCATION"), ("lat=200&lng=105", "INVALID_LOCATION"),
                      ("lat=abc&lng=105", "INVALID_LOCATION"), ("radius=1000", "INVALID_LOCATION"), ("limit=0", "INVALID_PARAMETER"),
                      ("limit=abc", "INVALID_PARAMETER"), ("cursor=-1", "INVALID_PARAMETER"), ("q=" + "x" * 101, "INVALID_PARAMETER"),
                      ("category=<x>", "INVALID_PARAMETER")):
        r = client.get(f"/api/m4l/discovery?{bad}")
        check(r.status_code == 400 and r.json["code"] == code, f"tham số sai → 400 {code}: {bad[:30]}")

    # ---- visibility rules
    ex("UPDATE pois SET status='hidden' WHERE id=?", (hk[1],))
    check(hk[1] not in {i["id"] for i in client.get("/api/m4l/discovery?mood=chay-deadline").json["items"]}, "địa điểm bị ẩn không xuất hiện")
    ex("UPDATE pois SET status='published' WHERE id=?", (hk[1],))
    ex("INSERT INTO cms_pins(poi_id,active,approved_at,expires_at,created_at) VALUES(?,1,?,?,?)", (other, now() - 100, now() - 10, now()))
    check(other not in {i["id"] for i in client.get("/api/m4l/discovery?mood=chay-deadline").json["items"]}, "ghim hết hạn không xuất hiện")
    check(client.put(f"/api/m4l/admin/moods/{stress}", headers=admin, json={"status": "inactive"}).status_code == 200, "S0 tắt mood")
    check("xa-stress" not in [m["slug"] for m in client.get("/api/m4l/moods").json["items"]], "mood tắt không còn công khai")
    check(client.get("/api/m4l/discovery?mood=xa-stress").status_code == 404, "mood tắt → 404 khi lọc")
    check("xa-stress" not in next(i for i in client.get("/api/m4l/discovery?mood=chay-deadline").json["items"] if i["id"] == hk[0])["moods"],
          "mood tắt không hiện trong nhãn địa điểm")
    check(any(m["slug"] == "xa-stress" for m in client.get("/api/m4l/admin/moods", headers=admin).json["items"]), "admin vẫn thấy mood đã tắt")

    # ---- cascade & content hygiene
    ex("DELETE FROM pois WHERE id=?", (hk[0],))
    check(not q("SELECT 1 FROM m4l_poi_moods WHERE poi_id=?", (hk[0],), one=True), "xóa địa điểm xóa liên kết mood (FK cascade)")
    web = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "web" / "m4l").iterdir())
    check(all(s not in web for s in ("Giang", "15%", "60 phút", "CẦU GIẤY")), "giao diện không hardcode tên/số liệu mockup")

    # ---- downgrade & re-migrate
    m4l_migrations.downgrade(0, log=lambda m: None)
    check(not m4l_tables(), "downgrade gỡ toàn bộ bảng m4l_*")
    check(q("SELECT COUNT(*) n FROM users", one=True)["n"] == users_before and q("SELECT COUNT(*) n FROM pois", one=True)["n"] == pois_before - 1,
          "downgrade không đụng bảng cũ")
    check(m4l.init_m4l(log=lambda m: None) and q("SELECT COUNT(*) n FROM m4l_moods", one=True)["n"] == 4, "migrate lại sau downgrade")

    # ---- flag off again
    os.environ.pop("XANH24_M4L_ENABLED")
    check(client.get("/api/m4l/home").status_code == 404 and client.get("/m4l").status_code == 404, "tắt cờ lại: M4L ẩn ngay")
    check(client.get("/").status_code == 200, "tắt cờ: bản đồ vẫn chạy")
    print(f"\nM4L Phase 1: {passed} kiểm thử đạt")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
    shutil.rmtree(scratch, ignore_errors=True)
