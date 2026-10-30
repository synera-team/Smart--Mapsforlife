"""M4L 2.0 Phase 2: random pick quota/repetition, Fog of War grid + GPS validation, mystery pins."""
import math
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="m4l-p2-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "m4l.db"),
    "XANH24_SECRET": "m4l-p2-test-secret-not-for-production", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
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
    import m4l_exploration as geo
    from db import ex, now, q, set_setting

    app = create_app()
    client = app.test_client()
    base_cfg = {"unlock_min_interval_s": 0, "random_cooldown_s": 0}
    set_setting("m4l_config", base_cfg)

    def cms_login(username, password, section):
        response = client.post("/api/cms/login", json={"username": username, "password": password, "section": section})
        assert response.status_code == 200, response.json
        return {"Authorization": "Bearer " + response.json["token"]}

    def register(username):
        r = client.post("/api/cms/register", json={"username": username, "password": "User@20261", "full_name": f"Người {username}",
                                                     "birth_date": "2000-01-01", "gender": "undisclosed", "email": f"{username}@example.com",
                                                     "phone": "0912345678"})
        assert r.status_code == 201, r.json
        return {"Authorization": "Bearer " + r.json["token"]}

    admin = cms_login("admin", "Admin@2026x", "admin")
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "noidung", "password": "Content@2026", "wards": ["hoan-kiem"]}).status_code == 200
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "caugiay", "password": "Content@2026", "wards": ["cau-giay"]}).status_code == 200
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "AREA", "username": "khuvuc", "password": "Area@2026x", "wards": ["cau-giay"]}).status_code == 200
    content_hk = cms_login("noidung", "Content@2026", "admin")
    content_cg = cms_login("caugiay", "Content@2026", "admin")
    area_staff = cms_login("khuvuc", "Area@2026x", "manager")
    alice, bob, carol = register("alice"), register("bobby"), register("carol")

    # ---- pilot area from the real ward boundary
    area = q("SELECT * FROM m4l_areas WHERE slug='cau-giay'", one=True)
    cells_db = q("SELECT COUNT(*) n FROM m4l_cells WHERE area_id=? AND grid_version=1", (area["id"],), one=True)["n"]
    check(area and area["status"] == "active" and area["cell_size_m"] == 100, "migration tạo khu vực thí điểm Cầu Giấy, ô 100 m")
    check(area["eligible_cell_count"] == cells_db and 200 < cells_db < 800, f"mẫu số = số ô đủ điều kiện trong ranh giới ({cells_db} ô)")
    check(client.get("/m4l/world").status_code == 200, "/m4l/world hiển thị")

    # ---- grid ids are stable and boundary-exact
    dlat, dlng = geo.grid_step(area["cell_size_m"], area["ref_lat"])
    gx, gy = 1055000, 210400
    check(geo.cell_of(gy * dlat + 1e-9, gx * dlng + 1e-9, area)[0] == f"{gx}:{gy}", "điểm ngay trên cạnh dưới-trái thuộc ô đó")
    check(geo.cell_of(gy * dlat - 1e-9, gx * dlng - 1e-9, area)[0] == f"{gx - 1}:{gy - 1}", "điểm ngay dưới cạnh thuộc ô kề")
    check(geo.cell_of(21.03, 105.79, area) == geo.cell_of(21.03, 105.79, dict(area)), "mã ô ổn định giữa các lần tính")

    PILOT = "?area=cau-giay"
    explore = client.get("/api/m4l/exploration" + PILOT).json
    check(explore["area"]["slug"] == "cau-giay" and explore["level"] == "cells" and len(explore["cells"]) == cells_db, "khách xem được lưới khu vực pilot")
    check(explore["unlocked"] == [] and explore["progress"] is None, "khách không có ô đã mở hay tiến độ")
    # pilot cells that are also unlockable in the city grid (same ids), so both areas record the visit
    both = [r["cell_id"] for r in q("SELECT p.cell_id FROM m4l_cells p JOIN m4l_cells c ON c.cell_id=p.cell_id AND c.grid_version=1 "
                                    "AND c.status IN ('eligible','pending_review') AND c.area_id=(SELECT id FROM m4l_areas WHERE slug='ha-noi') "
                                    "WHERE p.area_id=? ORDER BY p.gy, p.gx", (area["id"],))]
    cx, cy = map(int, both[len(both) // 2].split(":"))
    center = geo.cell_center(cx, cy, area)
    cx2, cy2 = map(int, both[len(both) // 2 + 1].split(":"))
    center2 = geo.cell_center(cx2, cy2, area)

    def samples(lat, lng, acc=12, n=2, step_s=5, drift_m=0):
        t = time.time() * 1000
        return [{"lat": lat + i * drift_m / 111320, "lng": lng, "accuracy": acc, "t": t - (n - 1 - i) * step_s * 1000} for i in range(n)]

    def unlock(headers, body):
        return client.post("/api/m4l/exploration/unlock", headers=headers, json={"area": "cau-giay", **body})

    # ---- unlock validation (T08–T10)
    check(unlock({}, {"samples": samples(*center)}).status_code == 401, "mở khóa cần đăng nhập")
    check(unlock(area_staff, {"samples": samples(*center)}).status_code == 403, "tài khoản nhân viên không mở khóa")
    r = unlock(alice, {"samples": samples(*center, acc=80)})
    check(r.status_code == 422 and r.json["code"] == "LOCATION_TOO_INACCURATE", "sai số GPS > 50 m: không mở khóa, có lý do")
    check(unlock(alice, {"samples": samples(*center, n=1)}).json["code"] == "INSUFFICIENT_SAMPLES", "một lần đo: chưa đủ")
    check(unlock(alice, {"samples": samples(*center, drift_m=150)}).json["code"] == "LOCATION_INCONSISTENT", "các lần đo lệch nhau: từ chối")
    check(unlock(alice, {"samples": samples(*center, step_s=1, drift_m=70)}).json["code"] == "IMPLAUSIBLE_MOVEMENT", "tốc độ phi lý giữa các lần đo")
    check(unlock(alice, {"samples": "x"}).json["code"] == "INVALID_LOCATION", "payload mẫu sai → INVALID_LOCATION")
    check(unlock(alice, {"samples": [{"lat": 999, "lng": 1, "accuracy": 5, "t": 0}] * 2}).status_code == 400, "tọa độ ngoài miền → 400")
    check(not q("SELECT 1 FROM m4l_user_unlocks", one=True), "mẫu không hợp lệ không ghi ô nào")

    r = unlock(alice, {"samples": samples(*center), "account_id": 999})
    check(r.status_code == 200 and r.json["unlocked"] and not r.json["already_unlocked"], "mẫu hợp lệ mở khóa ô")
    first_cell = r.json["cell_id"]
    check(r.json["progress"]["unlocked"] == 1 and r.json["progress"]["eligible"] == cells_db, "tiến độ có mẫu số rõ ràng")
    check(r.json["progress"]["percentage"] == round(100 / cells_db, 4), "phần trăm = ô đã mở / ô đủ điều kiện")
    r = unlock(alice, {"samples": samples(*center)})
    check(r.status_code == 200 and r.json["already_unlocked"], "mở lại cùng ô: already_unlocked")
    check(q("SELECT COUNT(*) n FROM m4l_user_unlocks WHERE area_id=?", (area["id"],), one=True)["n"] == 1, "chỉ một bản ghi cho mỗi ô")
    check(client.get("/api/m4l/exploration/progress" + PILOT, headers=bob).json["unlocked"] == 0, "người khác không được mở hộ (bỏ qua account_id trong body)")
    check(client.get("/api/m4l/exploration" + PILOT, headers=alice).json["unlocked"] == [first_cell], "tải lại vẫn giữ ô đã mở")
    home_p = client.get("/api/m4l/home", headers=alice).json["progress"]
    check(home_p["area"]["slug"] == "ha-noi" and home_p["unlocked"] + home_p["unlocked_pending"] == 1, "ô mở ở pilot cũng được ghi cho Hà Nội; Home lấy tiến độ từ DB")

    far = (center[0] + 0.05, center[1])  # ~5.5 km away seconds later
    check(unlock(alice, {"samples": samples(*far)}).json["code"] == "IMPLAUSIBLE_MOVEMENT", "dịch chuyển tức thời so với lần trước: từ chối")
    check(unlock(carol, {"samples": samples(21.0287, 105.8524)}).json["code"] == "OUTSIDE_AREA", "vị trí ngoài khu vực thí điểm: từ chối")
    state = q("SELECT * FROM m4l_location_state WHERE account_id=(SELECT id FROM cms_accounts WHERE username='alice')", one=True)
    check(state["lat"] == round(state["lat"], 4) and q("SELECT COUNT(*) n FROM m4l_location_state", one=True)["n"] <= 3,
          "chỉ lưu một vị trí gần nhất (làm tròn ~11 m), không lưu lịch sử")

    set_setting("m4l_config", {**base_cfg, "unlock_min_interval_s": 30})
    check(unlock(bob, {"samples": samples(*center2)}).status_code == 200, "lần thử đầu của người khác hợp lệ")
    check(unlock(bob, {"samples": samples(*center2)}).json["code"] == "RATE_LIMITED", "thử liên tục bị giới hạn tần suất")
    set_setting("m4l_config", base_cfg)

    # ---- mystery pins (FR-04)
    hk_poi = q("SELECT id FROM pois WHERE ward_slug='hoan-kiem' AND status='published' LIMIT 1", one=True)["id"]
    check(client.post("/api/m4l/admin/pins", headers=content_hk, json={"area": "cau-giay", "lat": center[0], "lng": center[1], "teaser": "x"}).status_code == 403,
          "CONTENT ngoài phường không tạo ghim")
    check(client.post("/api/m4l/admin/pins", headers=alice, json={"area": "cau-giay"}).status_code == 403, "USER không tạo ghim")
    r = client.post("/api/m4l/admin/pins", headers=admin, json={"area": "cau-giay", "lat": 21.0287, "lng": 105.8524, "teaser": "x"})
    check(r.status_code == 400 and r.json["code"] == "OUTSIDE_AREA", "ghim ngoài khu vực → 400")
    exact = (center[0] + dlat * 0.3, center[1] + dlng * 0.3)
    r = client.post("/api/m4l/admin/pins", headers=content_cg, json={"area": "cau-giay", "lat": exact[0], "lng": exact[1],
                                                                       "teaser": "Có gì đó thú vị ở đây", "reveal_title": "Góc sách nhỏ", "reveal_text": "Chi tiết"})
    check(r.status_code == 201 and r.json["status"] == "draft", "CONTENT trong phường tạo ghim (bản nháp)")
    pin_id = r.json["id"]
    check(client.get("/api/m4l/mystery-pins" + PILOT).json["items"] == [], "ghim nháp không hiển thị")
    check(client.put(f"/api/m4l/admin/pins/{pin_id}", headers=content_cg, json={"status": "published"}).status_code == 200, "xuất bản ghim")
    guest_pin = client.get("/api/m4l/mystery-pins" + PILOT).json["items"][0]
    check(not guest_pin["unlocked"] and "reveal_title" not in guest_pin and "poi" not in guest_pin, "ghim chưa mở chỉ có lời gợi ý")
    check(abs(guest_pin["lat"] - exact[0]) > 1e-6, "ghim chưa mở không lộ tọa độ chính xác (chỉ tâm ô)")
    mine = client.get("/api/m4l/mystery-pins" + PILOT, headers=alice).json["items"][0]
    check(mine["unlocked"] and mine["reveal_title"] == "Góc sách nhỏ" and mine["lat"] == exact[0], "người đã mở ô thấy nội dung ghim")
    check(not client.get("/api/m4l/mystery-pins" + PILOT, headers=bob).json["items"][0]["unlocked"], "người chưa mở ô vẫn thấy ghim bị khóa")
    r = client.post("/api/m4l/admin/pins", headers=admin, json={"area": "cau-giay", "lat": exact[0], "lng": exact[1], "teaser": "POI", "poi_id": hk_poi, "status": "published"})
    check(r.status_code == 201, "ghim liên kết địa điểm công khai")
    ex("UPDATE pois SET status='hidden' WHERE id=?", (hk_poi,))
    check(len(client.get("/api/m4l/mystery-pins" + PILOT).json["items"]) == 1, "địa điểm liên kết bị ẩn → ghim ẩn theo")
    ex("UPDATE pois SET status='published' WHERE id=?", (hk_poi,))
    check(q("SELECT COUNT(*) n FROM audit WHERE action LIKE 'm4l.pin.%'", one=True)["n"] == 3, "thao tác ghim ghi audit")

    # ---- forget my exploration (consent withdrawal)
    check(client.delete("/api/m4l/exploration/me", headers=bob).status_code == 200, "người dùng xóa dữ liệu khám phá")
    check(client.get("/api/m4l/exploration/progress" + PILOT, headers=bob).json["unlocked"] == 0
          and not q("SELECT 1 FROM m4l_location_state WHERE account_id=(SELECT id FROM cms_accounts WHERE username='bobby')", one=True),
          "xóa cả ô đã mở và vị trí gần nhất")

    # ---- random (FR-02, T06)
    check(client.post("/api/m4l/discovery/random", json={}).status_code == 401, "random cần đăng nhập")
    check(client.post("/api/m4l/discovery/random", headers=area_staff, json={}).status_code == 403, "nhân viên không dùng random")
    r = client.post("/api/m4l/discovery/random", headers=alice, json={})
    check(r.status_code == 200 and r.json["item"] is None, "chưa POI nào gắn mood: random không gợi ý bừa trụ sở hành chính")
    deadline = q("SELECT id FROM m4l_moods WHERE slug='chay-deadline'", one=True)["id"]
    pool = [r["id"] for r in q("SELECT id FROM pois WHERE status='published' AND lat IS NOT NULL ORDER BY id LIMIT 3")]
    for pid in pool:
        assert client.put(f"/api/m4l/admin/pois/{pid}/moods", headers=admin, json={"moods": [{"id": deadline}]}).status_code == 200
    picks = []
    for _ in range(3):
        r = client.post("/api/m4l/discovery/random", headers=alice, json={"mood": "chay-deadline"})
        assert r.status_code == 200, r.json
        picks.append(r.json["item"]["id"])
    check(sorted(picks) == sorted(pool), "mỗi lần đúng 1 địa điểm, không lặp trong 24 giờ")
    check(r.json["item"]["sponsored"] is False and "Chọn ngẫu nhiên" in r.json["reason"], "kết quả organic, có lý do chọn")
    r = client.post("/api/m4l/discovery/random", headers=alice, json={"mood": "chay-deadline"})
    check(r.status_code == 200 and r.json["item"]["id"] in pool and "lặp lại" in r.json["reason"], "hết địa điểm mới: cho lặp và nói rõ")
    r = client.post("/api/m4l/discovery/random", headers=alice, json={"mood": "hen-ho"})
    check(r.status_code == 200 and r.json["item"] is None and r.json["code"] == "NO_ELIGIBLE_POI", "pool rỗng → không kết quả, báo rõ")
    events = q("SELECT COUNT(*) n FROM m4l_discovery_events WHERE channel='random'", one=True)["n"]
    check(events == 4, "pool rỗng không tốn lượt; mỗi lượt được ghi log")
    check(client.post("/api/m4l/discovery/random", headers=alice, json={"mood": "Bad!"}).status_code == 400, "tham số random sai → 400")

    set_setting("m4l_config", {**base_cfg, "random_daily_quota": 5})
    check(client.post("/api/m4l/discovery/random", headers=alice, json={}).status_code == 200, "lượt thứ 5 trong hạn mức")
    r = client.post("/api/m4l/discovery/random", headers=alice, json={})
    check(r.status_code == 429 and r.json["code"] == "QUOTA_EXCEEDED", "vượt hạn mức 24 giờ → 429")

    set_setting("m4l_config", {**base_cfg, "random_cooldown_s": 30})
    results = []

    def spin():
        with app.test_client() as own:
            results.append(own.post("/api/m4l/discovery/random", headers=carol, json={}).status_code)

    threads = [threading.Thread(target=spin) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check(sorted(results) == [200, 429, 429, 429], f"bấm dồn dập song song: chỉ 1 kết quả ({results})")
    check(q("SELECT COUNT(*) n FROM m4l_discovery_events WHERE account_id=(SELECT id FROM cms_accounts WHERE username='carol')", one=True)["n"] == 1,
          "không ghi lượt trùng do race")
    set_setting("m4l_config", base_cfg)

    # ---- grid version change (T11)
    check(client.post(f"/api/m4l/admin/areas/{area['id']}/regenerate", headers=content_cg, json={"cell_size_m": 200}).status_code == 403,
          "CONTENT không đổi lưới")
    r = client.post(f"/api/m4l/admin/areas/{area['id']}/regenerate", headers=admin, json={"cell_size_m": 200})
    check(r.status_code == 200 and r.json["grid_version"] == 2 and r.json["eligible_cell_count"] < cells_db, "đổi kích thước ô → grid_version mới")
    p = client.get("/api/m4l/exploration/progress" + PILOT, headers=alice).json
    check(p["grid_version"] == 2 and p["eligible"] == r.json["eligible_cell_count"] and p["unlocked"] == 0, "tiến độ tính theo phiên bản lưới hiện tại")
    check(q("SELECT COUNT(*) n FROM m4l_user_unlocks WHERE grid_version=1", one=True)["n"] >= 1, "ô đã mở ở lưới cũ được giữ lại")
    r = client.post("/api/m4l/admin/areas", headers=admin, json={"slug": "nghia-do", "name": "Nghĩa Đô", "ward_slugs": ["nghia-do"]})
    check(r.status_code == 201 and r.json["eligible_cell_count"] > 0, "S0 tạo khu vực mới từ ranh giới phường")
    check(client.post("/api/m4l/admin/areas", headers=admin, json={"slug": "x-y", "name": "X", "ward_slugs": ["khong-co"]}).status_code == 400,
          "phường không có ranh giới → 400")
    check(client.put(f"/api/m4l/admin/areas/{r.json['id']}", headers=admin, json={"status": "inactive"}).json["status"] == "inactive", "tắt khu vực")
    check(client.get("/api/m4l/exploration?area=nghia-do").status_code == 404, "khu vực tắt không hiển thị")
    print(f"\nM4L Phase 2: {passed} kiểm thử đạt")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
    shutil.rmtree(scratch, ignore_errors=True)
