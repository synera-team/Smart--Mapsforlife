"""Kiểm thử luồng chính: đăng nhập, phân quyền S0/S1/CW, phê duyệt, import Excel có ảnh."""
import io, json, os, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ["XANH24_DATA_DIR"] = tmp
os.environ["XANH24_DB"] = os.path.join(tmp, "t.db")
os.environ["XANH24_ADMIN_PASSWORD"] = "Admin@2026x"
sys.path.insert(0, os.path.join(ROOT, "server"))
import db; db.UPLOAD_DIR = os.path.join(tmp, "uploads")
import media; media.UPLOAD_DIR = db.UPLOAD_DIR
from app import create_app
app = create_app(); c = app.test_client()
ok = 0
def check(cond, msg):
    global ok
    if not cond:
        print("FAIL:", msg); sys.exit(1)
    ok += 1; print("  ✓", msg)

def login(u, p):
    r = c.post("/api/auth/login", json={"username": u, "password": p}); return r
r = login("admin", "wrong"); check(r.status_code == 401, "sai mật khẩu bị từ chối")
r = login("admin", "Admin@2026x"); check(r.status_code == 200 and r.json["user"]["role"] == "S0", "S0 đăng nhập")
H0 = {"Authorization": "Bearer " + r.json["token"]}
check(c.get("/api/admin/stats").status_code == 401, "API quản trị yêu cầu đăng nhập")
r = c.post("/api/admin/users", headers=H0, json={"username": "duyet", "password": "Duyet@2026", "role": "S1", "full_name": "Cán bộ duyệt"})
check(r.status_code == 200, "S0 tạo tài khoản S1")
r = c.post("/api/admin/users", headers=H0, json={"username": "nhaplieu", "password": "Nhap@2026", "role": "CW", "wards": ["hoan-kiem", "cua-nam"]})
check(r.status_code == 200, "S0 tạo Co-worker giới hạn 2 phường")
check(c.post("/api/admin/users", headers=H0, json={"username": "yeu", "password": "123", "role": "CW"}).status_code == 400, "chặn mật khẩu yếu")
H1 = {"Authorization": "Bearer " + login("duyet", "Duyet@2026").json["token"]}
HC = {"Authorization": "Bearer " + login("nhaplieu", "Nhap@2026").json["token"]}
check(c.get("/api/admin/users", headers=H1).status_code == 403, "S1 không quản lý người dùng")
check(c.put("/api/admin/settings", headers=HC, json={"idle_timeout": 60}).status_code == 403, "CW không sửa cấu hình")
# CW đề xuất thêm mới
poi = {"name": "Điểm thử nghiệm", "category": "dich-vu-cong", "lat": 21.0299, "lng": 105.8510, "description": "abc",
       "vr360": {"type": "embed", "url": "https://kuula.co/share/collection/abc"}}
r = c.post("/api/admin/pois", headers=HC, json={"data": poi, "mode": "publish"})
check(r.status_code == 200 and r.json["status"] == "pending", "CW không thể tự publish → chờ duyệt")
rid = r.json["revision_id"]
pub = c.get("/api/public/pois").json["items"]
check(not any(p["name"] == "Điểm thử nghiệm" for p in pub), "chưa duyệt thì chưa hiển thị công khai")
r = c.post("/api/admin/pois", headers=HC, json={"data": {**poi, "lat": 21.07, "lng": 105.80}, "mode": "submit"})
check(r.status_code == 403, "CW bị chặn nhập ngoài phạm vi phường")
check(c.post(f"/api/admin/revisions/{rid}/approve", headers=HC).status_code == 403, "CW không tự duyệt")
check(c.post(f"/api/admin/revisions/{rid}/reject", headers=H1, json={}).status_code == 400, "từ chối phải có lý do")
r = c.post(f"/api/admin/revisions/{rid}/approve", headers=H1, json={"note": "OK"})
check(r.status_code == 200, "S1 duyệt")
pub = c.get("/api/public/pois").json["items"]
p = [x for x in pub if x["name"] == "Điểm thử nghiệm"]
check(p and p[0]["ward_slug"] == "hoan-kiem" and p[0]["has_vr"], "hiển thị công khai, tự gán phường theo ranh giới, có VR360")
pid = p[0]["id"]
d = c.get(f"/api/public/pois/{pid}").json
check(d["vr360"]["type"] == "embed" and d["code"].startswith("X24-"), "chi tiết có VR360 và mã")
# sửa bởi CW -> bản live giữ nguyên
r = c.put(f"/api/admin/pois/{pid}", headers=HC, json={"data": {"name": "Điểm đã sửa"}, "mode": "submit"})
check(r.status_code == 200 and r.json["status"] == "pending", "CW gửi yêu cầu sửa")
check(c.get(f"/api/public/pois/{pid}").json["name"] == "Điểm thử nghiệm", "bản công khai giữ nguyên khi chờ duyệt")
r = c.post("/api/admin/revisions/bulk", headers=H1, json={"ids": [r.json["revision_id"]], "action": "approve"})
check(r.json["ok"] == 1 and c.get(f"/api/public/pois/{pid}").json["name"] == "Điểm đã sửa", "duyệt hàng loạt áp dụng thay đổi")
# S1 publish trực tiếp
r = c.post("/api/admin/pois", headers=H1, json={"data": {**poi, "name": "S1 đăng trực tiếp"}, "mode": "publish"})
check(r.json["status"] == "approved", "S1 publish trực tiếp")
# xoá vĩnh viễn chỉ S0
check(c.delete(f"/api/admin/pois/{pid}?purge=1", headers=H1).status_code == 403, "S1 không xoá vĩnh viễn")
check(c.delete(f"/api/admin/pois/{pid}?purge=1", headers=H0).status_code == 200, "S0 xoá vĩnh viễn")
# Excel import
tpl = c.get("/api/admin/import/template")
check(tpl.status_code == 200 and len(tpl.data) > 5000, "tải biểu mẫu Excel")
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
wb = openpyxl.load_workbook(io.BytesIO(tpl.data))
ws = wb["DIA_DIEM"]
ws.append(["", "Nhà văn hoá tổ dân phố 5", "Dịch vụ công", "Phường Cửa Nam", "12 Hàng Bài", 21.0235, 105.8530, 912345678.0,
           "07:00-21:00", "", "Sinh hoạt cộng đồng", "", "anh2.jpg;https://example.com/a.jpg", "Nhúng (iframe)",
           "https://my.matterport.com/show/?m=abc", "văn hoá", "Culture house", "x"])
ws.append(["", "Toạ độ Google", "Y tế", "", "", "21.0290, 105.8520", "", "", "", "", "", "", "", "Ảnh 360", "pano.jpg", "", "", ""])
ws.append(["", "Lỗi danh mục", "Không có", "", "", 21.03, 105.85])
ws.append(["", "Ngoài VN", "Y tế", "", "", 48.85, 2.35])
img = Image.new("RGB", (320, 200), (30, 120, 200)); b = io.BytesIO(); img.save(b, "PNG"); b.seek(0)
xi = XLImage(b); ws.add_image(xi, "L4")
out = io.BytesIO(); wb.save(out)
zb = io.BytesIO()
import zipfile
with zipfile.ZipFile(zb, "w") as z:
    ib = io.BytesIO(); Image.new("RGB", (100, 100), (0, 200, 100)).save(ib, "JPEG"); z.writestr("anh2.jpg", ib.getvalue())
    pb = io.BytesIO(); Image.new("RGB", (2000, 1000), (90, 90, 160)).save(pb, "JPEG"); z.writestr("pano.jpg", pb.getvalue())
r = c.post("/api/admin/import/preview", headers=HC, data={"file": (io.BytesIO(out.getvalue()), "dl.xlsx"), "zip": (io.BytesIO(zb.getvalue()), "a.zip")},
           content_type="multipart/form-data")
check(r.status_code == 200, "xem trước import")
rows = r.json["rows"]
print("   rows:", [(x["row"], x["data"]["name"], x["errors"], len(x["data"]["images"])) for x in rows])
r0 = [x for x in rows if x["data"]["name"] == "Nhà văn hoá tổ dân phố 5"][0]
print("   r0:", r0["data"]["phone"], r0["data"]["vr360"], r0["warnings"])
check(len(r0["data"]["images"]) == 3 and r0["data"]["phone"] == "0912345678" and r0["data"]["vr360"]["type"] == "embed", "nhận ảnh chèn trong dòng + ảnh zip + link, VR360 nhúng, SĐT")
r1 = [x for x in rows if x["data"]["name"] == "Toạ độ Google"][0]
check(abs(r1["data"]["lng"] - 105.852) < 1e-6 and r1["data"]["vr360"]["type"] == "pano", "tách toạ độ dán dạng chuỗi, VR ảnh 360 từ zip")
check(len([x for x in rows if x["errors"]]) == 2, "phát hiện 2 dòng lỗi")
r = c.post(f"/api/admin/import/{r.json['batch_id']}/commit", headers=HC, json={"mode": "submit"})
check(r.json["done"] == 2 and r.json["skipped"] == 2, "gửi phê duyệt 2 dòng hợp lệ")
pend = c.get("/api/admin/revisions?status=pending", headers=H1).json["items"]
check(len(pend) == 2, "S1 thấy 2 yêu cầu chờ duyệt")
# route fallback & events
r = c.get("/api/public/route?from=105.85,21.03&to=105.84,21.02&mode=foot")
check(r.status_code == 200 and r.json["distance"] > 0, f"định tuyến trả kết quả ({r.json['source']})")
check(c.post("/api/public/events", json={"device": "HK-01", "events": [{"type": "poi_view", "poi_id": 1}]}).json["stored"] == 1, "ghi nhận thống kê")
check(c.get("/api/admin/stats", headers=HC).status_code == 200, "dashboard thống kê")
check(c.get("/api/public/wards.geojson").json["features"][0]["geometry"]["type"] == "Polygon", "GeoJSON ranh giới")
# ward geometry permission
check(c.put("/api/admin/wards/hoan-kiem", headers=H1, json={"geometry": {"type": "Polygon", "coordinates": []}}).status_code == 403, "S1 không sửa ranh giới")
# api key read-only
k = c.post("/api/admin/apikeys", headers=H0, json={"name": "test"}).json["key"]
check(c.get("/api/admin/pois", headers={"X-API-Key": k}).status_code == 200, "API key đọc được")
check(c.post("/api/admin/pois", headers={"X-API-Key": k}, json={"data": poi}).status_code == 403, "API key không ghi được")
# chọn điểm bất kỳ + phiên bản dữ liệu cho kiosk
import geocode
geocode.reverse = lambda settings, lat, lng, lang="vi": {"name": "", "address": "12 Phố Hàng Bài, Hà Nội", "road": "Phố Hàng Bài"}
r = c.get("/api/public/reverse?lat=21.0288&lng=105.8525")
check(r.status_code == 200 and r.json["ward_slug"] == "hoan-kiem" and r.json["address"], "tra điểm bất kỳ: phường + địa chỉ")
check(c.get("/api/public/reverse?lat=abc").status_code == 400, "tra điểm: kiểm tra tham số")
v1 = c.get("/api/public/version").json["data_version"]
import time as _t; _t.sleep(1.1)
c.put("/api/admin/settings", headers=H0, json={"idle_timeout": 45})
check(c.get("/api/public/version").json["data_version"] > v1, "data_version tăng khi dữ liệu thay đổi (kiosk tự cập nhật)")
check("data_version" in c.get("/api/public/bootstrap").json, "bootstrap có data_version")
# tìm địa chỉ bất kỳ + định vị Wi-Fi cho kiosk
geocode.search = lambda settings, q, lat=0, lng=0, lang="vi", limit=8: [{"name": "Phố Huế", "address": "Hai Bà Trưng, Hà Nội", "lat": 21.0125, "lng": 105.8516, "kind": "street"}]
r = c.get("/api/public/geocode?q=pho hue")
check(r.status_code == 200 and r.json["items"][0]["name"] == "Phố Huế" and "ward_slug" in r.json["items"][0], "tìm địa chỉ bất kỳ")
geocode.wifi_locate = lambda settings, wifi, cells=None: {"lat": 21.0245, "lng": 105.848, "acc": 25, "src": "wifi-google"} if len(wifi) >= 2 else None
r = c.post("/api/public/geolocate", json={"wifi": [{"mac": "aa:bb:cc:dd:ee:01", "rssi": -50}, {"mac": "aa:bb:cc:dd:ee:02", "rssi": -70}]})
check(r.status_code == 200 and abs(r.json["lat"] - 21.0245) < 1e-6 and r.json["acc"] == 25, "định vị kiosk qua Wi-Fi")
check(c.post("/api/public/geolocate", json={"wifi": []}).status_code == 404, "Wi-Fi rỗng → báo không xác định được")
print(f"\nTẤT CẢ {ok} KIỂM THỬ ĐẠT")
shutil.rmtree(tmp)
