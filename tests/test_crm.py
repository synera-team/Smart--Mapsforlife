"""Kiểm thử module Xanh24 CRM: phân quyền, khách hàng, hợp đồng, thanh toán, việc cần làm, báo cáo quảng cáo."""
import os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ["XANH24_DATA_DIR"] = tmp
os.environ["XANH24_DB"] = os.path.join(tmp, "t.db")
os.environ["XANH24_ADMIN_PASSWORD"] = "Admin@2026x"
sys.path.insert(0, os.path.join(ROOT, "server"))
import db; db.UPLOAD_DIR = os.path.join(tmp, "uploads")
from app import create_app
app = create_app(); c = app.test_client()
ok = 0


def check(cond, msg):
    global ok
    if not cond:
        print("FAIL:", msg); sys.exit(1)
    ok += 1; print("  ✓", msg)


def tok(u, p):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": u, "password": p}).json["token"]}


H0 = tok("admin", "Admin@2026x")
c.post("/api/admin/users", headers=H0, json={"username": "duyet", "password": "Duyet@2026", "role": "S1"})
c.post("/api/admin/users", headers=H0, json={"username": "sale", "password": "Sale@2026x", "role": "CW", "full_name": "NV Kinh doanh"})
H1, HC = tok("duyet", "Duyet@2026"), tok("sale", "Sale@2026x")
P = "/api/modules/crm"

check(c.get(P + "/overview").status_code == 401, "CRM yêu cầu đăng nhập")
r = c.get(P + "/meta", headers=HC)
check(r.status_code == 200 and "advertiser" in r.json["kinds"] and r.json["users"], "CW xem danh mục CRM")
me = c.get("/api/auth/me", headers=HC).json["user"]
check("crm.read" in me["permissions"] and "crm.finance" not in me["permissions"], "quyền CRM có trong ma trận quyền")

r = c.post(P + "/customers", headers=HC, json={"name": "Cà phê Hồ Gươm", "kind": "advertiser", "phone": "0901234567", "expected_value": 24000000})
check(r.status_code == 200, "CW thêm khách hàng tiềm năng")
cid = r.json["id"]
check(c.post(P + "/customers", headers=HC, json={"kind": "advertiser"}).status_code == 400, "bắt buộc tên khách hàng")
check(c.post(P + "/customers", headers=HC, json={"name": "X", "stage": "abc"}).status_code == 400, "chặn giai đoạn sai")
check(c.put(f"{P}/customers/{cid}", headers=HC, json={"stage": "quoted"}).status_code == 200, "chuyển giai đoạn → đã báo giá")
r = c.get(P + "/customers?q=hồ gươm", headers=HC)
check(len(r.json["items"]) == 1 and r.json["items"][0]["stage"] == "quoted", "tìm kiếm khách hàng")

# hợp đồng: CW không được, S1 được
ct = {"customer_id": cid, "kind": "ads", "title": "Quảng cáo 3 tháng", "value": 24000000, "status": "active",
      "start_at": int(time.time()) - 86400, "end_at": int(time.time()) + 20 * 86400, "device_codes": ["HK-01"]}
check(c.post(P + "/contracts", headers=HC, json=ct).status_code == 403, "CW không tạo hợp đồng")
check(c.post(P + "/contracts", headers=H1, json={**ct, "end_at": ct["start_at"] - 10}).status_code == 400, "kiểm tra ngày hợp đồng")
# quảng cáo gắn hợp đồng
r = c.post("/api/admin/ads", headers=H1, json={"title": "Banner Cà phê", "media_type": "image", "media_url": "/assets/logo.webp", "publish": True})
ad = r.json["id"]
r = c.post(P + "/contracts", headers=H1, json={**ct, "ad_ids": [ad]})
check(r.status_code == 200, "S1 tạo hợp đồng quảng cáo")
kid = r.json["id"]
cust = c.get(f"{P}/customers/{cid}", headers=HC).json
check(cust["customer"]["stage"] == "won", "hợp đồng hiệu lực → khách chuyển 'đã ký'")
check(cust["contracts"][0]["code"].startswith("HD-") and cust["contracts"][0]["expiring"], "tự sinh mã HĐ + cảnh báo sắp hết hạn")
check(c.post(f"{P}/contracts/{kid}/payments", headers=H1, json={"amount": 0}).status_code == 400, "chặn thanh toán 0đ")
check(c.post(f"{P}/contracts/{kid}/payments", headers=H1, json={"amount": 10000000, "method": "Chuyển khoản"}).status_code == 200, "ghi nhận thanh toán")
lst = c.get(P + "/contracts", headers=HC).json["items"]
check(lst[0]["paid"] == 10000000 and lst[0]["due"] == 14000000, "tính đã thu / còn nợ")

# việc cần làm
r = c.post(P + "/activities", headers=HC, json={"customer_id": cid, "kind": "call", "title": "Gọi xác nhận nội dung", "due_at": int(time.time()) - 86400 * 2})
aid = r.json["id"]
r = c.post(P + "/activities", headers=HC, json={"customer_id": cid, "kind": "note", "content": "Khách muốn thêm video 15s"})
check(r.status_code == 200, "ghi chú nhật ký")
op = c.get(P + "/activities?status=open", headers=HC).json["items"]
check(len(op) == 1 and op[0]["overdue"], "việc quá hạn được đánh dấu")
check(c.post(f"{P}/activities/{aid}/done", headers=HC, json={}).status_code == 200 and
      not c.get(P + "/activities?status=open", headers=HC).json["items"], "hoàn thành việc")

# sự kiện hiển thị quảng cáo từ kiosk
c.post("/api/admin/devices", headers=H1, json={"code": "HK-01", "name": "Kiosk Hồ Gươm"})
c.post("/api/public/events", json={"device": "HK-01", "session": "s1", "events": [{"type": "session_start"}] + [{"type": "ad_impression", "data": {"ad": ad}}] * 5})
c.post("/api/public/heartbeat", json={"device": "HK-01"})
ov = c.get(P + "/overview", headers=HC).json
check(ov["today"]["impressions"] == 5 and ov["kiosks"]["online"] == 1, "tổng quan: lượt hiển thị hôm nay + kiosk trực tuyến")
check(ov["money"]["month_paid"] == 10000000 and ov["money"]["receivable"] == 14000000, "tổng quan: doanh thu tháng, công nợ")
check(ov["top_ads"][0]["n"] == 5 and ov["expiring"], "tổng quan: top quảng cáo, HĐ sắp hết hạn")
dv = c.get(P + "/devices", headers=HC).json["items"]
check(dv[0]["today"]["impressions"] == 5 and dv[0]["contracts"][0]["id"] == kid, "màn hình: số liệu + hợp đồng gắn máy")
rep = c.get(f"{P}/report?contract={kid}", headers=HC).json
check(rep["total"] == 5 and rep["devices"][0]["code"] == "HK-01", "báo cáo theo hợp đồng")
csv = c.get(f"{P}/report?customer={cid}&format=csv", headers=HC)
check(csv.status_code == 200 and "Banner Cà phê" in csv.get_data(as_text=True), "xuất CSV báo cáo")
r = c.post(P + "/refresh", headers=HC)
check(r.status_code == 200 and r.json["token"], "gia hạn phiên màn hình CRM")
check(c.get("/crm/").status_code == 200, "trang /crm/ phục vụ được")

check(c.delete(f"{P}/customers/{cid}", headers=HC).status_code == 403, "CW không xoá khách hàng")
check(c.delete(f"{P}/customers/{cid}", headers=H1).status_code == 200 and not c.get(P + "/contracts", headers=H1).json["items"], "S1 xoá khách hàng + hợp đồng")
print(f"\nTẤT CẢ {ok} KIỂM THỬ CRM ĐẠT")
