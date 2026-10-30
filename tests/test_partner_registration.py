"""Partner submission, regional inbox and private documents."""

import io
import json
import os
import sys
import tempfile
from email import policy
from email.parser import BytesParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="xanh24-partner-") as scratch_name:
    scratch = Path(scratch_name)
    os.environ.update({
        "XANH24_DATA_DIR": str(scratch),
        "XANH24_DB": str(scratch / "cms.db"),
        "XANH24_SECRET": "partner-test-secret-not-for-production",
        "XANH24_ADMIN_PASSWORD": "Admin@2026x",
        "CMS_MAIL_MODE": "outbox",
    })
    sys.path.insert(0, str(ROOT / "server"))
    from app import create_app
    from db import q

    client = create_app().test_client()

    def login(username, password, section):
        response = client.post("/api/cms/login", json={
            "username": username, "password": password, "section": section,
        })
        assert response.status_code == 200, response.json
        return {"Authorization": "Bearer " + response.json["token"]}

    admin = login("admin", "Admin@2026x", "admin")
    for username, ward in (("manager_a", "hoan-kiem"), ("manager_b", "ba-dinh")):
        response = client.post("/api/cms/accounts", headers=admin, json={
            "role": "AREA", "username": username, "password": "Manager@2026", "wards": [ward],
        })
        assert response.status_code == 200, response.json
    manager_a = login("manager_a", "Manager@2026", "manager")
    manager_b = login("manager_b", "Manager@2026", "manager")
    options = client.get("/api/cms/partner-registration/options").json
    assert {ward["slug"] for ward in options["wards"]} == {"hoan-kiem", "ba-dinh"}
    assert any(category["id"] == "an-uong" for category in options["categories"])

    def submission(ward="hoan-kiem", filename="license.pdf", content=b"%PDF-1.4\nDemo license"):
        return {
            "owner_name": "Người đại diện", "email": "partner@example.com", "phone": "0912345678",
            "representative_role": "owner", "business_name": "Thương hiệu thử nghiệm",
            "category": "an-uong", "ward_slug": ward, "address": "12 Hàng Bạc, Hoàn Kiếm, Hà Nội",
            "opening_days": ["mon", "tue", "wed"], "opening_time": "08:00", "closing_time": "22:00",
            "documents": [(io.BytesIO(content), filename)],
        }

    endpoint = "/api/cms/partner-registration"
    assert client.post(endpoint, data=submission(ward="tay-ho")).status_code == 400
    assert client.post(endpoint, data=submission(filename="license.exe")).status_code == 400
    created = client.post(endpoint, data=submission())
    assert created.status_code == 201, created.json
    aid = created.json["id"]
    assert client.get("/api/cms/applications", headers=manager_b).json["items"] == []
    visible = client.get("/api/cms/applications", headers=manager_a).json["items"]
    assert len(visible) == 1 and visible[0]["id"] == aid
    assert visible[0]["answers"]["category"] == "an-uong"
    assert "path" not in visible[0]["answers"]["documents"][0]

    file_url = f"/api/cms/applications/{aid}/files/0"
    assert client.get(file_url).status_code == 401
    assert client.get(file_url, headers=manager_b).status_code == 404
    downloaded = client.get(file_url, headers=manager_a)
    assert downloaded.status_code == 200 and downloaded.data.startswith(b"%PDF-1.4")
    stored = json.loads(q("SELECT answers FROM cms_applications WHERE id=?", (aid,), one=True)["answers"])
    assert client.get("/uploads/" + stored["documents"][0]["path"]).status_code == 404

    decision = {"action": "approve", "note": "Đã đối chiếu giấy tờ", "category": "an-uong",
                "lat": 21.0299, "lng": 105.851}
    assert client.post(f"/api/cms/applications/{aid}/review", headers=manager_b, json=decision).status_code == 404
    assert client.post(f"/api/cms/applications/{aid}/review", headers=manager_a, json=decision).status_code == 400
    assert client.post(f"/api/cms/applications/{aid}/review", headers=manager_a,
                       json={**decision, "username": "manager_a", "password": "Partner@2026"}).status_code == 409
    decision.update(username="thuong_hieu_hoan_kiem", password="Partner@2026")
    approved = client.post(f"/api/cms/applications/{aid}/review", headers=manager_a, json=decision)
    assert approved.status_code == 200 and approved.json["status"] == "approved", approved.json
    assert q("SELECT status,account_id,poi_id FROM cms_applications WHERE id=?", (aid,), one=True)["account_id"]
    login("thuong_hieu_hoan_kiem", "Partner@2026", "kiosk")
    mailed = list((scratch / "cms-mail-outbox").glob("*.eml"))
    assert len(mailed) == 1
    message = BytesParser(policy=policy.default).parsebytes(mailed[0].read_bytes())
    assert "thuong_hieu_hoan_kiem" in message.get_content()
    from db import _local
    _local.conn.close()
    _local.conn = None
    print("Partner registration and regional document checks passed")
