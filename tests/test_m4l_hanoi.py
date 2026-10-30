"""M4L Fog of War across the whole of Hanoi: v2→v3 migration, city grid, multi-district unlocks, viewport API, zones, pins."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="m4l-hn-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "m4l.db"),
    "XANH24_SECRET": "m4l-hn-test-secret-not-for-production", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
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
    import m4l_migrations
    from db import ex, now, q, set_setting

    app = create_app()
    client = app.test_client()
    set_setting("m4l_config", {"unlock_min_interval_s": 0, "random_cooldown_s": 0})

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

    admin = cms_login("admin", "Admin@2026x", "admin")
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "caugiay", "password": "Content@2026", "wards": ["cau-giay"]}).status_code == 200
    content_cg = cms_login("caugiay", "Content@2026", "admin")
    walker, walker_id = register("walker")
    racer, _ = register("racer")
    pioneer, pioneer_id = register("pioneer")

    # ---- v2 → v3 migration keeps pilot progress (run on this test DB: roll back v3, add a pilot unlock, migrate again)
    pilot = q("SELECT * FROM m4l_areas WHERE slug='cau-giay'", one=True)
    m4l_migrations.downgrade(2, log=lambda m: None)
    check(not q("SELECT 1 FROM m4l_areas WHERE slug='ha-noi'", one=True), "rollback v3 gỡ khu vực thành phố, giữ pilot")
    pilot_cell = q("SELECT cell_id FROM m4l_cells WHERE area_id=? ORDER BY gy, gx LIMIT 1 OFFSET 200", (pilot["id"],), one=True)["cell_id"]
    ex("INSERT INTO m4l_user_unlocks(account_id,area_id,grid_version,cell_id,unlocked_at,validation_method) VALUES(?,?,1,?,?,'gps')",
       (pioneer_id, pilot["id"], pilot_cell, now() - 86400))
    m4l_migrations.migrate(log=lambda m: None)
    city = q("SELECT * FROM m4l_areas WHERE slug='ha-noi'", one=True)
    carried = q("SELECT * FROM m4l_user_unlocks WHERE account_id=? AND area_id=?", (pioneer_id, city["id"]), one=True)
    check(carried and carried["cell_id"] == pilot_cell and carried["validation_method"] == "migrated:cau-giay", "ô đã mở ở Cầu Giấy được chuyển sang Hà Nội (cùng mã ô)")
    check(q("SELECT 1 FROM m4l_user_unlocks WHERE account_id=? AND area_id=?", (pioneer_id, pilot["id"]), one=True), "lịch sử mở khóa pilot vẫn giữ nguyên")
    check(q("SELECT COUNT(*) n FROM m4l_cells WHERE area_id=?", (pilot["id"],), one=True)["n"] == 402, "giữ nguyên 402 ô Cầu Giấy")
    check(list((scratch / "backups").glob("m4l-v3-report-*.json")) and list((scratch / "backups").glob("*pre-m4l-v*.db")), "có báo cáo migration và bản sao lưu trước khi chạy lại v3 (nhãn theo phiên bản cuối của lần chạy)")
    m4l_migrations.migrate(log=lambda m: None)
    check(q("SELECT COUNT(*) n FROM m4l_areas WHERE slug='ha-noi'", one=True)["n"] == 1, "chạy lại migration không nhân bản khu vực")

    # ---- city grid covers Hanoi, not Cầu Giấy
    meta = json.loads(q("SELECT meta FROM m4l_area_sources WHERE area_id=?", (city["id"],), one=True)["meta"])
    cells = q("SELECT COUNT(*) n FROM m4l_cells WHERE area_id=?", (city["id"],), one=True)["n"]
    eligible = q("SELECT COUNT(*) n FROM m4l_cells WHERE area_id=? AND status='eligible'", (city["id"],), one=True)["n"]
    check(city["kind"] == "city" and cells == meta["cells"] and 320_000 < cells < 350_000, f"lưới phủ toàn Hà Nội: {cells:,} ô ≈ {cells / 100:,.0f} km²")
    check(q("SELECT COUNT(*) n FROM m4l_units", one=True)["n"] == 126, "126 phường/xã (51 phường + 75 xã)")
    check(q("SELECT COUNT(DISTINCT unit_slug) n FROM m4l_cells WHERE area_id=?", (city["id"],), one=True)["n"] == 126, "ô thuộc đủ 126 đơn vị, kể cả ngoại thành")
    check(city["eligible_cell_count"] == eligible and eligible != 402, "mẫu số là số ô hợp lệ toàn thành phố, không phải 402")
    check("ODbL" in meta["license"] and meta["crs"].startswith("EPSG:4326") and meta["osm_timestamp"], "có nguồn, giấy phép, hệ tọa độ, mốc dữ liệu")
    check(client.get("/api/m4l/home").json["area"]["slug"] == "ha-noi", "khu vực mặc định là Hà Nội; Cầu Giấy chỉ là pilot")
    bnd = client.get("/api/m4l/areas/ha-noi/boundary").json
    check(bnd["boundary"]["type"] == "MultiPolygon" and "ODbL" in bnd["meta"]["license"], "API ranh giới thành phố kèm nguồn")
    ring = max((poly[0] for poly in bnd["boundary"]["coordinates"]), key=len)
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    check(len(ring) >= 50 and max(xs) - min(xs) > 0.5 and max(ys) - min(ys) > 0.5, f"ranh giới hiển thị đủ chi tiết ({len(ring)} điểm, phủ cả thành phố)")

    # ---- viewport API never ships the whole city
    t0 = time.time()
    overview = client.get("/api/m4l/exploration?area=ha-noi")
    t_overview = time.time() - t0
    check(overview.json["level"] == "blocks" and "cells" not in overview.json and len(overview.get_data()) < 400_000,
          f"không bbox: trả {len(overview.json['blocks']):,} khối 1 km ({len(overview.get_data()) / 1024:.0f} KB), không trả 337 nghìn ô")
    cg = (21.0335, 105.7945)
    small = f"{cg[1] - .01:.4f},{cg[0] - .008:.4f},{cg[1] + .01:.4f},{cg[0] + .008:.4f}"
    t0 = time.time()
    view = client.get(f"/api/m4l/exploration?area=ha-noi&bbox={small}").json
    t_cells = time.time() - t0
    check(view["level"] == "cells" and 0 < len(view["cells"]) <= view["max_view_cells"], f"zoom gần: {len(view['cells'])} ô trong khung nhìn")
    whole = "105.2,20.5,106.1,21.4"
    check(client.get(f"/api/m4l/exploration?area=ha-noi&bbox={whole}&level=cells").json["code"] == "VIEWPORT_TOO_LARGE", "ép tải từng ô cho cả thành phố → 400")
    check(client.get(f"/api/m4l/exploration?area=ha-noi&bbox={whole}").json["level"] == "blocks", "khung nhìn lớn tự chuyển sang khối")
    check(client.get("/api/m4l/exploration?area=ha-noi&bbox=1,2,3").status_code == 400, "bbox sai → 400")
    check(t_overview < 3 and t_cells < 1.5, f"thời gian phản hồi: tổng quan {t_overview * 1000:.0f} ms, khung nhìn {t_cells * 1000:.0f} ms")

    # ---- one account unlocking across districts accumulates progress
    def pick(unit, statuses=("eligible", "pending_review")):
        rows = q(f"SELECT cell_id, gx, gy, status FROM m4l_cells WHERE area_id=? AND unit_slug=? AND status IN ({','.join('?' * len(statuses))}) "
                 "ORDER BY CASE status WHEN 'eligible' THEN 0 ELSE 1 END, gy, gx LIMIT 1", (city["id"], unit, *statuses))
        return rows[0] if rows else None

    def samples(lat, lng, acc=12):
        t = time.time() * 1000
        return [{"lat": lat, "lng": lng, "accuracy": acc, "t": t - 5000}, {"lat": lat + 2e-5, "lng": lng, "accuracy": acc, "t": t}]

    def unlock(headers, lat, lng, acc=12):
        return client.post("/api/m4l/exploration/unlock", headers=headers, json={"samples": samples(lat, lng, acc)})

    def travel(account_id):  # pretend hours pass between trips so the teleport check does not apply
        ex("UPDATE m4l_location_state SET fix_at=fix_at-7200 WHERE account_id=?", (account_id,))

    rural = q("SELECT slug FROM m4l_units WHERE kind='xa' AND slug IN (SELECT unit_slug FROM m4l_cells WHERE area_id=? AND status='eligible') ORDER BY slug LIMIT 1",
              (city["id"],), one=True) or q("SELECT slug FROM m4l_units WHERE kind='xa' ORDER BY slug LIMIT 1", one=True)
    visited = []
    for unit in ("cau-giay", "hoan-kiem", "long-bien", "ha-dong", rural["slug"]):
        cell = pick(unit)
        assert cell, unit
        lat, lng = geo.cell_center(cell["gx"], cell["gy"], city)
        before = client.get("/api/m4l/exploration/progress", headers=walker).json
        r = unlock(walker, lat, lng)
        after = client.get("/api/m4l/exploration/progress", headers=walker).json
        counted = cell["status"] == "eligible"
        check(r.status_code == 200 and r.json["cell_id"] == cell["cell_id"] and r.json["counted"] == counted
              and after["unlocked"] - before["unlocked"] == int(counted) and after["unlocked_pending"] - before["unlocked_pending"] == int(not counted),
              f"mở khóa tại {unit} ({cell['status']}) và cộng dồn vào cùng tài khoản")
        visited.append(cell["cell_id"])
        travel(walker_id)
    breakdown = client.get("/api/m4l/exploration/progress?breakdown=unit", headers=walker).json
    units_with_eligible = q("SELECT COUNT(DISTINCT unit_slug) n FROM m4l_cells WHERE area_id=? AND status='eligible'", (city["id"],), one=True)["n"]
    check(len(breakdown["units"]) == units_with_eligible and sum(u["unlocked"] for u in breakdown["units"]) == breakdown["unlocked"],
          "thống kê theo phường/xã khớp tổng")
    check(breakdown["complete"] == (breakdown["pending_review"] == 0), "cờ complete phản ánh còn ô chưa xác minh")
    check(breakdown["percentage"] == round(100 * breakdown["unlocked"] / breakdown["eligible"], 4), "phần trăm tính từ DB với mẫu số toàn thành phố")

    # ---- what must not count
    base = client.get("/api/m4l/exploration/progress", headers=walker).json
    for name, (lat, lng) in {"Bắc Ninh": (21.186, 106.076), "Hưng Yên": (20.646, 106.051), "Hòa Bình": (20.817, 105.338)}.items():
        r = unlock(walker, lat, lng)
        travel(walker_id)
        check(r.status_code == 422 and r.json["code"] == "OUTSIDE_AREA", f"vị trí ngoài Hà Nội ({name}) không mở khóa")
    water = q("SELECT gx, gy FROM m4l_cells WHERE area_id=? AND status='excluded' ORDER BY gy, gx LIMIT 1 OFFSET 500", (city["id"],), one=True)
    r = unlock(walker, *geo.cell_center(water["gx"], water["gy"], city))
    travel(walker_id)
    check(r.json["code"] == "CELL_NOT_COUNTED", "ô mặt nước không mở khóa, không tính")
    restricted = q("SELECT gx, gy FROM m4l_cells WHERE area_id=? AND status='restricted' LIMIT 1", (city["id"],), one=True)
    if restricted:
        r = unlock(walker, *geo.cell_center(restricted["gx"], restricted["gy"], city))
        travel(walker_id)
        check(r.json["code"] == "CELL_NOT_COUNTED", "ô khu hạn chế không mở khóa, không tính")
    r = unlock(walker, *geo.cell_center(*map(int, visited[0].split(":")), city), acc=120)
    travel(walker_id)
    check(r.json["code"] == "LOCATION_TOO_INACCURATE" and "chỗ thoáng" in r.json["error"], "GPS kém: không mở khóa, có hướng dẫn thử lại")
    after = client.get("/api/m4l/exploration/progress", headers=walker).json
    check((after["unlocked"], after["unlocked_pending"]) == (base["unlocked"], base["unlocked_pending"]), "các lần bị từ chối không làm đổi tiến độ")

    # ---- concurrent unlocks of the same cell
    target = pick("ba-dinh")
    lat, lng = geo.cell_center(target["gx"], target["gy"], city)
    results = []

    def go():
        with app.test_client() as own:
            results.append(own.post("/api/m4l/exploration/unlock", headers=racer, json={"samples": samples(lat, lng)}).status_code)

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = q("SELECT COUNT(*) n FROM m4l_user_unlocks WHERE area_id=? AND cell_id=? AND account_id=(SELECT id FROM cms_accounts WHERE username='racer')",
             (city["id"], target["cell_id"]), one=True)["n"]
    check(rows == 1 and results.count(200) >= 1, f"4 yêu cầu đồng thời cùng ô → 1 bản ghi ({results})")

    # ---- mystery pins anywhere in Hanoi
    far_cell = pick(rural["slug"])
    flat, flng = geo.cell_center(far_cell["gx"], far_cell["gy"], city)
    dlat, dlng = geo.grid_step(city["cell_size_m"], city["ref_lat"])
    exact = (flat + dlat * .3, flng + dlng * .3)
    r = client.post("/api/m4l/admin/pins", headers=admin, json={"area": "ha-noi", "lat": exact[0], "lng": exact[1], "teaser": "Bí mật ngoại thành",
                                                                 "reveal_title": "Đã tìm thấy", "status": "published"})
    check(r.status_code == 201, f"S0 tạo ghim bí ẩn ở xã ngoại thành ({rural['slug']})")
    near = f"{flng - .01:.4f},{flat - .01:.4f},{flng + .01:.4f},{flat + .01:.4f}"
    guest = client.get(f"/api/m4l/mystery-pins?area=ha-noi&bbox={near}").json["items"]
    check(len(guest) == 1 and not guest[0]["unlocked"] and "reveal_title" not in guest[0] and abs(guest[0]["lat"] - exact[0]) > 1e-6,
          "ghim chưa mở không lộ nội dung và tọa độ chính xác")
    check(client.get("/api/m4l/mystery-pins?area=ha-noi&bbox=105.80,21.02,105.82,21.04").json["items"] == [], "ghim lọc theo khung nhìn")
    mine = client.get(f"/api/m4l/mystery-pins?area=ha-noi&bbox={near}", headers=walker).json["items"][0]
    check(mine["unlocked"] and mine["reveal_title"] == "Đã tìm thấy", "người đã đến ô đó thấy nội dung ghim (server xác nhận)")
    check(client.post("/api/m4l/admin/pins", headers=admin, json={"area": "ha-noi", **dict(zip(("lat", "lng"), geo.cell_center(water["gx"], water["gy"], city))),
                                                                  "teaser": "x"}).json["code"] == "CELL_NOT_COUNTED", "không đặt ghim trên mặt nước")
    cg_cell, hk_cell = pick("cau-giay"), pick("hoan-kiem")
    r = client.post("/api/m4l/admin/pins", headers=content_cg, json={"area": "ha-noi", **dict(zip(("lat", "lng"), geo.cell_center(cg_cell["gx"], cg_cell["gy"], city))), "teaser": "CG"})
    check(r.status_code == 201, "CONTENT tạo ghim trong phường được giao trên lưới thành phố")
    r = client.post("/api/m4l/admin/pins", headers=content_cg, json={"area": "ha-noi", **dict(zip(("lat", "lng"), geo.cell_center(hk_cell["gx"], hk_cell["gy"], city))), "teaser": "HK"})
    check(r.status_code == 403 and not q("SELECT 1 FROM m4l_mystery_pins WHERE teaser='HK'", one=True), "CONTENT không tạo ghim ngoài phường được giao")
    check({p["teaser"] for p in client.get("/api/m4l/admin/pins", headers=content_cg).json["items"]} == {"CG"}, "CONTENT chỉ thấy ghim trong phạm vi")

    # ---- admin zones are versioned and reversible
    # a Cầu Giấy cell well inside both the OSM and the Xanh24 ward boundaries (they differ by a cell along the edge)
    zcell = q("SELECT c.gx, c.gy FROM m4l_cells c JOIN m4l_cells p ON p.cell_id=c.cell_id AND p.area_id=? WHERE c.area_id=? AND c.unit_slug='cau-giay' "
              "AND c.status IN ('eligible','pending_review') ORDER BY c.gy, c.gx LIMIT 1 OFFSET 150", (pilot["id"], city["id"]), one=True)
    zlat, zlng = geo.cell_center(zcell["gx"], zcell["gy"], city)
    square = {"type": "Polygon", "coordinates": [[[zlng - .002, zlat - .002], [zlng + .002, zlat - .002], [zlng + .002, zlat + .002], [zlng - .002, zlat + .002], [zlng - .002, zlat - .002]]]}
    check(client.post("/api/m4l/admin/zones", headers=content_cg, json={"area": "ha-noi", "name": "x", "kind": "restricted", "source": "x", "geometry": square}).status_code == 403,
          "CONTENT không khai báo vùng hạn chế")
    check(client.post("/api/m4l/admin/zones", headers=admin, json={"area": "ha-noi", "name": "x", "kind": "restricted", "geometry": square}).status_code == 400,
          "vùng hạn chế bắt buộc có nguồn căn cứ")
    before = client.get(f"/api/m4l/admin/areas/{city['id']}/stats", headers=admin).json
    r = client.post("/api/m4l/admin/zones", headers=admin, json={"area": "ha-noi", "name": "Khu thử nghiệm", "kind": "restricted",
                                                                  "source": "Kiểm thử tự động", "geometry": square})
    check(r.status_code == 201 and r.json["change"]["classification_version"] == city["classification_version"] + 1, "áp dụng vùng → tăng phiên bản phân loại")
    zone_id = r.json["zone"]["id"]
    mid = client.get(f"/api/m4l/admin/areas/{city['id']}/stats", headers=admin).json
    check(mid["totals"].get("restricted", 0) > before["totals"].get("restricted", 0) and mid["totals"]["eligible"] <= before["totals"]["eligible"],
          "ô trong vùng chuyển sang restricted, mẫu số tính lại")
    check(client.post("/api/m4l/exploration/unlock", headers=pioneer, json={"samples": samples(zlat, zlng)}).json["code"] == "CELL_NOT_COUNTED", "không mở khóa trong vùng hạn chế")
    client.put(f"/api/m4l/admin/zones/{zone_id}", headers=admin, json={"active": False})
    restored = client.get(f"/api/m4l/admin/areas/{city['id']}/stats", headers=admin).json
    check(restored["totals"] == before["totals"] and restored["area"]["classification_version"] == city["classification_version"] + 2, "tắt vùng → khôi phục phân loại gốc")
    log = client.get(f"/api/m4l/admin/areas/{city['id']}/changes", headers=admin).json["items"]
    check([c["action"] for c in log[:2]] == [f"zone.disable:{zone_id}", f"zone.create:{zone_id}"] and any(c["action"] == "area.import" for c in log), "nhật ký thay đổi lưới")
    check(q("SELECT COUNT(*) n FROM audit WHERE action LIKE 'm4l.zone.%'", one=True)["n"] == 2, "thao tác vùng ghi audit")

    # ---- admin tools
    ins = client.post("/api/m4l/admin/inspect", headers=content_cg, json={"lat": zlat, "lng": zlng}).json
    city_hit = next(a for a in ins["areas"] if a["area"] == "ha-noi")
    check(city_hit["in_area"] and city_hit["unit"]["slug"] == "cau-giay" and ins["xanh24_ward"] == "cau-giay", "công cụ tra tọa độ → ô, trạng thái, phường")
    check(client.post("/api/m4l/admin/inspect", headers=walker, json={"lat": 21, "lng": 105}).status_code == 403, "USER không dùng công cụ quản trị")
    st = client.get(f"/api/m4l/admin/areas/{city['id']}/stats", headers=admin).json
    check(len(st["units"]) == 126 and st["explorers"] >= 3 and st["cells"] == cells, "thống kê tổng hợp theo khu vực/phường")
    check(client.post(f"/api/m4l/admin/areas/{city['id']}/regenerate", headers=admin, json={"cell_size_m": 200}).json["code"] == "NOT_SUPPORTED",
          "không tạo lại lưới thành phố qua API")

    # ---- legacy keeps working
    for path in ("/", "/dashboard/user", "/admin", "/cms/login", "/hrm/login", "/m4l", "/m4l/world", "/m4l/admin", "/api/public/pois"):
        check(client.get(path).status_code == 200, f"không regression: {path}")
    print(f"\nM4L Hà Nội: {passed} kiểm thử đạt")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
    shutil.rmtree(scratch, ignore_errors=True)
