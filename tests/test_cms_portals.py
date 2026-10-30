"""Public user signup and split CMS/HRM routes."""

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
scratch = Path(tempfile.mkdtemp(prefix="cms-portals-", dir=TEST_DIR))
assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "cms.db"),
    "XANH24_SECRET": "cms-portal-test-secret-not-for-production",
    "XANH24_ADMIN_PASSWORD": "Admin@2026x",
})
sys.path.insert(0, str(ROOT / "server"))
sys.stdout.reconfigure(encoding="utf-8")

try:
    old = sqlite3.connect(scratch / "cms.db")
    old.execute("""CREATE TABLE cms_accounts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, full_name TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '',
      role TEXT NOT NULL CHECK(role IN ('AREA','CONTENT','REVIEW','OWNER')),
      wards TEXT DEFAULT '[]', active INTEGER DEFAULT 1, read_only INTEGER DEFAULT 0,
      created_by INTEGER, created_at INTEGER, last_login INTEGER)""")
    old.execute("INSERT INTO cms_accounts(username,password_hash,role,wards) VALUES('old_owner','unused','OWNER','[]')")
    old.commit()
    old.close()

    from app import create_app
    from db import q

    client = create_app().test_client()
    assert q("SELECT role FROM cms_accounts WHERE username='old_owner'", one=True)["role"] == "OWNER"
    for path in ("/cms/login", "/hrm/login", "/dashboard/user", "/dashboard/kiosk", "/dashboard/admin"):
        assert client.get(path).status_code == 200, path
    assert client.get("/cms").headers["Location"] == "/cms/login"
    home = client.get("/").get_data(as_text=True)
    assert 'href="/cms/login"' in home or 'src="/cms/map-login.js"' in home
    assert client.get("/cms/map-login.js").status_code == 200

    payload = {"username": "visitor", "password": "Visitor@2026", "full_name": "Người dùng thử",
               "birth_date": "2000-02-29", "gender": "undisclosed", "email": "visitor@example.com",
               "phone": "0912345678", "role": "OWNER"}
    assert client.post("/api/cms/register", json={**payload, "email": "wrong"}).status_code == 400
    assert client.post("/api/cms/register", json={**payload, "phone": "123"}).status_code == 400
    assert client.post("/api/cms/register", json={**payload, "birth_date": "2001-02-29"}).status_code == 400
    assert client.post("/api/cms/register", json={**payload, "gender": "other"}).status_code == 400
    assert client.post("/api/cms/register", json={**payload, "password": "weak"}).status_code == 400
    registered = client.post("/api/cms/register", json=payload)
    assert registered.status_code == 201, registered.json
    assert registered.json["user"]["role"] == "USER"
    assert registered.json["user"]["wards"] == []
    assert registered.json["user"]["birth_date"] == "2000-02-29"
    assert registered.json["user"]["gender"] == "undisclosed"
    assert registered.json["user"]["phone"] == "0912345678"
    assert client.post("/api/cms/register", json=payload).status_code == 400
    headers = {"Authorization": "Bearer " + registered.json["token"]}
    assert client.get("/api/cms/me", headers=headers).json["user"]["role"] == "USER"
    assert client.get("/api/cms/pins", headers=headers).status_code == 403
    assert client.get("/api/cms/content", headers=headers).status_code == 403
    assert client.get("/api/cms/orders", headers=headers).status_code == 403
    assert client.get("/api/cms/payments", headers=headers).status_code == 403
    assert client.get("/api/cms/accounts", headers=headers).status_code == 403

    login = lambda section, password: client.post("/api/cms/login", json={"section": section, "username": "visitor", "password": password})
    assert login("user", "Visitor@2026").status_code == 200
    assert login("kiosk", "Visitor@2026").status_code == 401
    assert login("admin", "Visitor@2026").status_code == 401
    profile = {"full_name": "Tên mới", "email": "new@example.com", "phone": "+84912345678",
               "birth_date": "1999-12-31", "gender": "female", "new_password": "NewPass@2026"}
    assert client.put("/api/cms/profile", headers=headers, json={**profile, "current_password": "wrong"}).status_code == 401
    updated = client.put("/api/cms/profile", headers=headers, json={**profile, "current_password": "Visitor@2026"})
    assert updated.status_code == 200 and updated.json["user"]["full_name"] == "Tên mới", updated.json
    assert updated.json["user"]["birth_date"] == "1999-12-31" and updated.json["user"]["gender"] == "female"
    assert updated.json["user"]["phone"] == "+84912345678"
    assert login("user", "Visitor@2026").status_code == 401
    assert login("user", "NewPass@2026").status_code == 200
    assert q("SELECT role,wards FROM cms_accounts WHERE username='visitor'", one=True)["role"] == "USER"
    print("CMS public user and portal route checks passed")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to(TEST_DIR.resolve())
    shutil.rmtree(scratch)
