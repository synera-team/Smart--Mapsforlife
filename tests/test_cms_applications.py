"""Registration intake, ward review, kiosk creation and email outbox checks."""

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
scratch = Path(tempfile.mkdtemp(prefix="cms-applications-", dir=ROOT / "tests"))
assert scratch.resolve().is_relative_to((ROOT / "tests").resolve())
os.environ.update({
    "XANH24_DATA_DIR": str(scratch), "XANH24_DB": str(scratch / "cms.db"),
    "XANH24_SECRET": "application-test-secret-long-enough-for-hs256", "XANH24_ADMIN_PASSWORD": "Admin@2026x",
    "CMS_FORMS_WEBHOOK_SECRET": "only-the-form-owner-knows-this-secret",
    "CMS_MAIL_MODE": "outbox", "CMS_SMTP_FROM": "demo@example.com",
})
sys.path.insert(0, str(ROOT / "server"))
sys.stdout.reconfigure(encoding="utf-8")

try:
    # Exercise the schema upgrade used by existing installations.
    db = sqlite3.connect(scratch / "cms.db")
    db.execute("""CREATE TABLE cms_accounts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, full_name TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '',
      role TEXT NOT NULL CHECK(role IN ('AREA','CONTENT','OWNER')),
      wards TEXT DEFAULT '[]', active INTEGER DEFAULT 1, read_only INTEGER DEFAULT 0,
      created_by INTEGER, created_at INTEGER, last_login INTEGER)""")
    db.execute("""CREATE TABLE cms_applications(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT UNIQUE NOT NULL,
      answers TEXT NOT NULL DEFAULT '{}', email TEXT DEFAULT '', owner_name TEXT DEFAULT '',
      business_name TEXT DEFAULT '', tax_id TEXT DEFAULT '', license_file TEXT DEFAULT '',
      phone TEXT DEFAULT '', address TEXT DEFAULT '', ward_slug TEXT,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
      review_note TEXT DEFAULT '', reviewed_by TEXT, reviewed_at INTEGER,
      account_id INTEGER UNIQUE, poi_id INTEGER UNIQUE,
      email_status TEXT DEFAULT 'none', email_error TEXT DEFAULT '', emailed_at INTEGER,
      submitted_at INTEGER NOT NULL, created_at INTEGER NOT NULL)""")
    db.commit()
    db.close()

    from app import create_app

    client = create_app().test_client()
    from cms_registration_wards import registration_ward_slug, registration_wards

    form_choices = """Ba Đình|Bạch Mai|Bồ Đề|Cầu Giấy|Chương Mỹ|Cửa Nam|Đại Mỗ|Định Công|Đông Ngạc|Đống Đa|Dương Nội|Giảng Võ|Hà Đông|Hai Bà Trưng|Hoàng Liệt|Hoàng Mai|Hoàn Kiếm|Hồng Hà|Khương Đình|Kiến Hưng|Kim Liên|Láng|Lĩnh Nam|Long Biên|Nghĩa Đô|Ngọc Hà|Ô Chợ Dừa|Phú Diễn|Phú Lương|Phú Thượng|Phúc Lợi|Phương Liệt|Sơn Tây|Tây Mỗ|Tây Hồ|Tây Tựu|Thanh Liệt|Thanh Xuân|Thượng Cát|Tùng Thiện|Tương Mai|Từ Liêm|Văn Miếu - Quốc Tử Giám|Việt Hưng|Vĩnh Hưng|Vĩnh Tuy|Xuân Đỉnh|Xuân Phương|Yên Hòa|Yên Nghĩa|Yên Sở""".split("|")
    assert len(form_choices) == 51
    assert all(registration_ward_slug(name) for name in form_choices)
    assert {name for _, name in registration_wards()} == set(form_choices)

    def call(method, path, token=None, body=None, secret=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if secret:
            headers["X-CMS-Webhook-Secret"] = secret
        return client.open(path, method=method, headers=headers, json=body)

    def login(username, password, section):
        response = call("POST", "/api/cms/login", body={"username": username, "password": password, "section": section})
        assert response.status_code == 200, response.json
        return response.json["token"]

    admin = login("admin", "Admin@2026x", "admin")
    made = call("POST", "/api/cms/accounts", admin, {"role": "REVIEW", "username": "wardreview",
                 "password": "Reviewer@2026", "wards": ["hoan-kiem"]})
    assert made.status_code == 200, made.json
    assert call("POST", "/api/cms/accounts", admin, {"role": "REVIEW", "username": "invalidreview",
                 "password": "Reviewer@2026", "wards": ["unknown-ward"]}).status_code == 400
    reviewer = login("wardreview", "Reviewer@2026", "review")
    assert call("GET", "/api/cms/wards", reviewer).status_code == 403
    assert [item["slug"] for item in call("GET", "/api/cms/registration-wards", reviewer).json["items"]] == ["hoan-kiem"]
    assert call("POST", "/api/cms/login", body={"username": "wardreview", "password": "Reviewer@2026", "section": "admin"}).status_code == 401
    assert call("GET", "/api/cms/accounts", reviewer).status_code == 403
    assert call("GET", "/api/cms/pins", reviewer).status_code == 403
    assert call("GET", "/api/cms/content", reviewer).status_code == 403
    assert call("POST", "/api/cms/applications/sync", reviewer).status_code == 403

    payload = {"source_id": "form:1", "email": "buyer@example.com", "owner_name": "Người mua",
               "business_name": "Doanh nghiệp A", "tax_id": "123456789", "license_file": "https://drive.google.com/file/d/sample/view",
               "answers": {"Mã số thuế": "123456789"}}
    intake = "/api/cms/applications/intake"
    assert call("POST", intake, body=payload).status_code == 401
    assert call("POST", "/api/cms/applications/sync", admin).status_code == 503
    import cms_applications
    os.environ["CMS_FORMS_PULL_URL"] = "https://script.google.com/macros/s/test/exec"
    os.environ["CMS_FORMS_PULL_SECRET"] = "test-pull-secret"
    original_urlopen = cms_applications.urlopen

    class GoogleResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return __import__("json").dumps({"items": [{**payload, "source_id": "form:pull"}]}).encode("utf-8")

    cms_applications.urlopen = lambda *_args, **_kwargs: GoogleResponse()
    sync = call("POST", "/api/cms/applications/sync", admin)
    assert sync.status_code == 200 and sync.json["created"] == 1, sync.json
    assert call("POST", "/api/cms/applications/sync", admin).json["duplicate"] == 1
    cms_applications.urlopen = original_urlopen
    response = call("POST", intake, body=payload, secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"])
    assert response.status_code == 200, response.json
    aid = response.json["id"]
    assert call("POST", intake, body=payload, secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["duplicate"]
    assert call("GET", "/api/cms/applications", reviewer).json["items"] == []
    assert len(call("GET", "/api/cms/applications", admin).json["items"]) == 2
    assert call("POST", f"/api/cms/applications/{aid}/assign", reviewer, {"ward": "hoan-kiem"}).status_code == 403
    assert call("POST", f"/api/cms/applications/{aid}/assign", admin, {"ward": "Hoàn Kiếm"}).status_code == 200
    assert len(call("GET", "/api/cms/applications", reviewer).json["items"]) == 1
    outside = call("POST", intake, body={**payload, "source_id": "form:outside", "ward": "Ba Đình"},
                   secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["id"]
    assert len(call("GET", "/api/cms/applications", reviewer).json["items"]) == 1
    assert call("POST", f"/api/cms/applications/{outside}/review", reviewer,
                {"action": "reject", "note": "No access"}).status_code == 404

    approve = {"action": "approve", "email": "buyer@example.com", "business_name": "Doanh nghiệp A",
               "address": "Hoàn Kiếm, Hà Nội", "lat": 21.0299, "lng": 105.851, "category": "dich-vu-cong",
               "note": "Đã đối chiếu hồ sơ kinh doanh"}
    review_url = f"/api/cms/applications/{aid}/review"
    assert call("POST", review_url, reviewer, {**approve, "lat": 21.0235, "lng": 105.853}).status_code == 409
    result = call("POST", review_url, reviewer, approve)
    assert result.status_code == 200 and result.json["email_status"] == "sent", result.json
    assert call("POST", review_url, reviewer, approve).status_code == 409
    application = call("GET", "/api/cms/applications", reviewer).json["items"][0]
    assert application["status"] == "approved" and application["poi_id"]
    assert not any(pin["id"] == application["poi_id"] for pin in client.get("/api/public/pois").json["items"])
    mail = next((scratch / "cms-mail-outbox").glob("*.eml")).read_text(encoding="utf-8")
    import email
    body = email.message_from_string(mail).get_payload(decode=True).decode("utf-8")
    username = next(line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("Tên đăng nhập"))
    password = next(line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("Mật khẩu:"))
    login(username, password, "kiosk")

    second = call("POST", intake, body={**payload, "source_id": "form:2",
                                       "answers": {"Phường": "Hoàn Kiếm", "Nhập địa chỉ Chi tiết": "12 Hàng Bạc"}},
                  secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["id"]
    second_row = next(item for item in call("GET", "/api/cms/applications", reviewer).json["items"] if item["id"] == second)
    assert second_row["ward_slug"] == "hoan-kiem" and second_row["address"] == "12 Hàng Bạc"
    rejected = call("POST", f"/api/cms/applications/{second}/review", reviewer,
                    {"action": "reject", "note": "Hồ sơ chưa hợp lệ"})
    assert rejected.status_code == 200 and rejected.json["email_status"] == "sent", rejected.json
    third = call("POST", intake, body={**payload, "source_id": "form:3", "ward": "Hoàn Kiếm"},
                 secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["id"]
    original_deliver = cms_applications.deliver

    def fail_mail(*_args):
        raise OSError("mail unavailable")

    cms_applications.deliver = fail_mail
    failed = call("POST", f"/api/cms/applications/{third}/review", reviewer, approve)
    assert failed.status_code == 200 and failed.json["email_status"] == "failed", failed.json
    cms_applications.deliver = original_deliver
    resent = call("POST", f"/api/cms/applications/{third}/resend", reviewer)
    assert resent.status_code == 200 and resent.json["email_status"] == "sent", resent.json
    fourth = call("POST", intake, body={**payload, "source_id": "form:4", "ward": "Hoàn Kiếm"},
                  secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["id"]
    del os.environ["CMS_MAIL_MODE"]
    assert call("POST", f"/api/cms/applications/{fourth}/review", reviewer, approve).status_code == 503
    assert next(item for item in call("GET", "/api/cms/applications", reviewer).json["items"] if item["id"] == fourth)["status"] == "pending"
    os.environ["CMS_MAIL_MODE"] = "outbox"
    # A previously synced response can gain its ward when the payload contains it.
    enriched = call("POST", intake, body={**payload, "source_id": "form:pull", "ward": "Phường Hoàn Kiếm",
                                                 "address": "12 Hàng Bạc"}, secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"])
    assert enriched.json["duplicate"]
    assert next(item for item in call("GET", "/api/cms/applications", reviewer).json["items"] if item["id"] == enriched.json["id"])["address"] == "12 Hàng Bạc"

    special_account = call("POST", "/api/cms/accounts", admin, {"role": "REVIEW", "username": "specialreview",
                          "password": "Reviewer@2026", "wards": ["van-mieu-quoc-tu-giam"]})
    assert special_account.status_code == 200, special_account.json
    special_reviewer = login("specialreview", "Reviewer@2026", "review")
    special = call("POST", intake, body={**payload, "source_id": "form:special", "ward": "Văn Miếu - Quốc Tử Giám"},
                   secret=os.environ["CMS_FORMS_WEBHOOK_SECRET"]).json["id"]
    assert any(item["id"] == special for item in call("GET", "/api/cms/applications", special_reviewer).json["items"])
    assert call("POST", f"/api/cms/applications/{special}/review", special_reviewer, approve).status_code == 409
    print("CMS application intake, scope, approval and email checks passed")
finally:
    if "db" in sys.modules:
        connection = getattr(sys.modules["db"]._local, "conn", None)
        if connection is not None:
            connection.close()
    assert scratch.resolve().is_relative_to((ROOT / "tests").resolve())
    shutil.rmtree(scratch)
