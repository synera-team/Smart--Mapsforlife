"""Exercise the CMS ownership, area scope, review and demo purchase lifecycle."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="cms-check-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ["XANH24_DATA_DIR"] = str(scratch)
os.environ["XANH24_DB"] = str(scratch / "cms.db")
os.environ["XANH24_SECRET"] = "cms-test-secret-not-for-production"
os.environ["XANH24_ADMIN_PASSWORD"] = "Admin@2026x"
sys.path.insert(0, str(ROOT / "server"))
sys.stdout.reconfigure(encoding="utf-8")

try:
    from app import create_app

    client = create_app().test_client()
    assert client.get("/cms").headers["Location"] == "/cms/login"
    assert client.get("/cms/login").status_code == 200
    assert client.get("/cms/cms.js").status_code == 200

    def auth(username, password, section):
        response = client.post("/api/cms/login", json={"username": username, "password": password, "section": section})
        assert response.status_code == 200, response.json
        return {"Authorization": "Bearer " + response.json["token"]}

    admin = auth("admin", "Admin@2026x", "admin")
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "AREA", "username": "manager", "password": "Manager@2026", "wards": ["hoan-kiem"]}).status_code == 200
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "reviewer", "password": "Review@2026", "wards": ["hoan-kiem"]}).status_code == 200
    assert client.post("/api/cms/accounts", headers=admin, json={"role": "CONTENT", "username": "elsewhere", "password": "Review@2026", "wards": ["cua-nam"]}).status_code == 200
    manager = auth("manager", "Manager@2026", "manager")
    reviewer = auth("reviewer", "Review@2026", "admin")
    elsewhere = auth("elsewhere", "Review@2026", "admin")
    assert client.post("/api/cms/accounts", headers=manager, json={"role": "CONTENT", "username": "illegal", "password": "Review@2026"}).status_code == 403
    payload = {"role": "OWNER", "username": "buyer", "password": "Buyer@2026", "full_name": "Người mua",
               "pin": {"name": "Ghim CMS", "address": "Hà Nội", "lat": 21.0299, "lng": 105.851, "category": "dich-vu-cong"}}
    response = client.post("/api/cms/accounts", headers=manager, json=payload)
    assert response.status_code == 200, response.json
    pin = response.json["pin_id"]
    assert client.put(f"/api/admin/pois/{pin}", headers=admin, json={"data": {"lat": 21.02}}).status_code == 403
    assert all(item["id"] != pin for item in client.get("/api/public/pois").json["items"])
    owner = auth("buyer", "Buyer@2026", "kiosk")
    assert client.post("/api/cms/content", headers=owner, json={"data": {"lat": 21}, "submit": True}).status_code == 400
    response = client.post("/api/cms/content", headers=owner, json={"data": {"name": "Ghim đã duyệt", "description": "Nội dung thử"}, "submit": True})
    assert response.status_code == 200, response.json
    revision = response.json["id"]
    assert client.post(f"/api/cms/content/{revision}/review", headers=elsewhere, json={"action": "approve"}).status_code == 404
    assert client.post(f"/api/cms/content/{revision}/review", headers=reviewer, json={"action": "approve"}).status_code == 200
    assert all(item["id"] != pin for item in client.get("/api/public/pois").json["items"])
    plan = client.get("/api/cms/plans", headers=owner).json["items"][0]
    order = client.post("/api/cms/orders", headers=owner, json={"plan_id": plan["id"]}).json["id"]
    assert client.post(f"/api/cms/orders/{order}/demo-pay", headers=owner).status_code == 200
    assert client.post(f"/api/cms/orders/{order}/demo-pay", headers=owner).status_code == 200
    assert sum(item["id"] == pin for item in client.get("/api/public/pois").json["items"]) == 1
    from db import ex, now
    ex("UPDATE cms_pins SET expires_at=? WHERE poi_id=?", (now() - 1, pin))
    assert all(item["id"] != pin for item in client.get("/api/public/pois").json["items"])
    renewal = client.post("/api/cms/orders", headers=owner, json={"plan_id": plan["id"]}).json["id"]
    assert client.post(f"/api/cms/orders/{renewal}/demo-pay", headers=owner).status_code == 200
    assert any(item["id"] == pin for item in client.get("/api/public/pois").json["items"])
    draft = client.post("/api/cms/content", headers=owner, json={"data": {"name": "Bản nháp"}}).json["id"]
    assert client.put(f"/api/cms/content/{draft}", headers=owner, json={"data": {"name": "Gửi lại"}, "submit": True}).json["status"] == "pending"
    assert len(client.get("/api/cms/payments", headers=manager).json["items"]) == 2
    assert client.post("/api/cms/kiosks", headers=admin, json={"code": "X1", "name": "Kiosk"}).status_code == 403
    assert client.post(f"/api/cms/pins/{pin}/active", headers=manager, json={"active": False}).status_code == 200
    assert client.post("/api/cms/content", headers=owner, json={"data": {"name": "Không được"}, "submit": True}).status_code == 403
    assert all(item["id"] != pin for item in client.get("/api/public/pois").json["items"])
    assert client.post("/api/cms/accounts", headers=manager, json={"role": "OWNER", "username": "buyer2", "password": "Buyer@2026", "pin_id": pin}).status_code == 200
    assert client.post("/api/cms/accounts", headers=manager, json={"role": "OWNER", "username": "buyer3", "password": "Buyer@2026", "pin_id": pin}).status_code == 400
    assert order in [item["id"] for item in client.get("/api/cms/orders", headers=owner).json["items"]]
    assert client.get("/api/cms/pins", headers=owner).json["items"] == []
    outside = client.post("/api/cms/accounts", headers=admin, json={
        "role": "OWNER", "username": "outsidebuyer", "password": "Buyer@2026",
        "pin": {"name": "Ghim khu vực khác", "address": "Cửa Nam", "lat": 21.0235, "lng": 105.853,
                "category": "dich-vu-cong"},
    })
    assert outside.status_code == 200, outside.json
    other_owner = auth("outsidebuyer", "Buyer@2026", "kiosk")
    other_order = client.post("/api/cms/orders", headers=other_owner, json={"plan_id": plan["id"]}).json["id"]
    assert client.post(f"/api/cms/orders/{other_order}/demo-pay", headers=other_owner).status_code == 200
    assert all(item["id"] != other_order for item in client.get("/api/cms/orders", headers=manager).json["items"])
    assert all(item["order_id"] != other_order for item in client.get("/api/cms/payments", headers=manager).json["items"])
    assert any(item["id"] == other_order for item in client.get("/api/cms/orders", headers=admin).json["items"])
    print("CMS lifecycle and scope checks passed")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
    shutil.rmtree(scratch)
