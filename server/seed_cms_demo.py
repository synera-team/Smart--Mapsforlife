"""Create disposable CMS demo accounts in the configured development database.

Run explicitly with ``python server/seed_cms_demo.py``. Credentials are written
only to the ignored data directory, never baked into the application.
"""

import os
import re
import secrets

from app import create_app
from auth import hash_password
from db import DATA_DIR, DB_PATH, ex, now, q


USERS = {
    "admin": ("cms_demo_admin", "admin"),
    "manager": ("cms_demo_manager", "manager"),
    "reviewer": ("cms_demo_reviewer", "admin"),
    "registration": ("cms_demo_registration", "review"),
    "buyer": ("cms_demo_buyer", "kiosk"),
}
FILE = os.path.join(DATA_DIR, "CMS_DEMO_ACCOUNTS.txt")


def call(client, method, path, *, headers=None, payload=None):
    response = client.open(path, method=method, headers=headers, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.get_json()}")
    return response.get_json()


def main():
    if os.path.exists(FILE):
        app = create_app()
        username = USERS["registration"][0]
        if q("SELECT 1 FROM cms_accounts WHERE username=?", (username,), one=True):
            print(f"Tài khoản demo đã được tạo: {FILE}")
            return
        with open(FILE, encoding="utf-8") as source:
            existing = source.read()
        match = re.search(r"^admin \(admin\): ([^\s]+) / (.+)$", existing, re.MULTILINE)
        if not match:
            raise RuntimeError("Không tìm thấy tài khoản demo Admin trong file")
        client = app.test_client()
        token = call(client, "POST", "/api/cms/login", payload={
            "username": match.group(1), "password": match.group(2), "section": "admin",
        })["token"]
        password = secrets.token_urlsafe(12) + "Aa1!"
        call(client, "POST", "/api/cms/accounts", headers={"Authorization": f"Bearer {token}"}, payload={
            "role": "REVIEW", "username": username, "password": password,
            "full_name": "CMS Demo Registration Reviewer", "wards": ["hoan-kiem"],
        })
        with open(FILE, "a", encoding="utf-8") as output:
            output.write(f"registration (review): {username} / {password}\n")
        print(f"Đã thêm tài khoản kiểm duyệt demo: {FILE}")
        return

    app = create_app()
    for username, _ in USERS.values():
        if q("SELECT 1 FROM users WHERE username=?", (username,), one=True) or q(
            "SELECT 1 FROM cms_accounts WHERE username=?", (username,), one=True
        ):
            raise RuntimeError(f"Tài khoản {username} đã tồn tại; không ghi đè mật khẩu")

    passwords = {kind: secrets.token_urlsafe(12) + "Aa1!" for kind in USERS}
    client = app.test_client()
    ex(
        "INSERT INTO users(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)",
        (USERS["admin"][0], hash_password(passwords["admin"]), "CMS Demo Admin", "S0", now()),
    )

    def login(kind):
        username, section = USERS[kind]
        token = call(client, "POST", "/api/cms/login", payload={
            "username": username, "password": passwords[kind], "section": section,
        })["token"]
        return {"Authorization": f"Bearer {token}"}

    admin = login("admin")
    call(client, "POST", "/api/cms/accounts", headers=admin, payload={
        "role": "AREA", "username": USERS["manager"][0],
        "password": passwords["manager"], "full_name": "CMS Demo Manager",
        "wards": ["hoan-kiem"],
    })
    call(client, "POST", "/api/cms/accounts", headers=admin, payload={
        "role": "CONTENT", "username": USERS["reviewer"][0],
        "password": passwords["reviewer"], "full_name": "CMS Demo Reviewer",
        "wards": ["hoan-kiem"],
    })
    call(client, "POST", "/api/cms/accounts", headers=admin, payload={
        "role": "REVIEW", "username": USERS["registration"][0],
        "password": passwords["registration"], "full_name": "CMS Demo Registration Reviewer",
        "wards": ["hoan-kiem"],
    })
    manager = login("manager")
    call(client, "POST", "/api/cms/accounts", headers=manager, payload={
        "role": "OWNER", "username": USERS["buyer"][0],
        "password": passwords["buyer"], "full_name": "CMS Demo Buyer",
        "pin": {"name": "Ghim CMS demo", "address": "Hoàn Kiếm, Hà Nội",
                "lat": 21.0299, "lng": 105.851, "category": "dich-vu-cong"},
    })
    login("reviewer")
    login("registration")
    login("buyer")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as output:
        output.write("CMS demo — " + DB_PATH + "\n\n")
        for kind, (username, section) in USERS.items():
            output.write(f"{kind} ({section}): {username} / {passwords[kind]}\n")
    print(f"Đã tạo 5 tài khoản demo. Thông tin đăng nhập: {FILE}")


if __name__ == "__main__":
    main()
