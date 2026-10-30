"""Google Form intake, ward-scoped registration review and email delivery."""

import hmac
import io
import json
import os
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flask import Blueprint, g, jsonify, request, send_file

from auth import hash_password, password_problem
from cms import PHONE_PATTERN, authenticate, error, role
from cms_registration_wards import registration_ward_slug
from db import DATA_DIR, IS_PG, connect, ex, load_media, now, q, row2dict, store_media


applications = Blueprint("cms_applications", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PARTNER_ROLES = {"owner", "legal_representative", "manager", "authorized_staff", "other"}
WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
DOCUMENT_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".doc": ("application/msword", bytes.fromhex("D0CF11E0A1B11AE1")),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
    ".jpg": ("image/jpeg", bytes.fromhex("FFD8FF")),
    ".jpeg": ("image/jpeg", bytes.fromhex("FFD8FF")),
    ".png": ("image/png", bytes.fromhex("89504E470D0A1A0A")),
    ".webp": ("image/webp", b"RIFF"),
}
MAX_DOCUMENTS = 8
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_APPLICATION_BYTES = 45 * 1024 * 1024


def public(row):
    result = row2dict(row, ("answers",))
    if isinstance(result.get("answers"), dict):
        documents = result["answers"].get("documents")
        if isinstance(documents, list):
            result["answers"]["documents"] = [
                {key: value for key, value in item.items() if key != "path"}
                for item in documents if isinstance(item, dict)
            ]
    return result


def mail_ready():
    if os.environ.get("CMS_MAIL_MODE") == "outbox":
        return True
    return all(os.environ.get(key) for key in
               ("CMS_SMTP_HOST", "CMS_SMTP_USER", "CMS_SMTP_PASSWORD", "CMS_SMTP_FROM", "CMS_PUBLIC_URL"))


def deliver(row, password=None):
    message = EmailMessage()
    message["From"] = os.environ.get("CMS_SMTP_FROM") or "CMS Demo <demo@localhost>"
    message["To"] = row["email"]
    message["Subject"] = "Kết quả đăng kí Ghim doanh nghiệp - Xanh24"
    status = "được duyệt" if row["status"] == "approved" else "chưa được duyệt"
    lines = [f"Kính gửi {row['owner_name'] or row['email']},", "",
             f"Hồ sơ đăng kí ghim cho {row['business_name']} đã {status}."]
    if row["review_note"]:
        lines += [f"Thông tin kiểm duyệt: {row['review_note']}"]
    if row["status"] == "approved":
        base = os.environ.get("CMS_PUBLIC_URL") or request.url_root.rstrip("/") + "/cms/login"
        lines += ["", f"Tên đăng nhập tài khoản kiosk: {row['username']}",
                  f"Mật khẩu: {password}", f"Trang đăng nhập: {base}",
                  "Chọn mục Tài khoản kiosk để đăng nhập. Sau khi đăng nhập, gửi nội dung ghim để kiểm duyệt và đăng kí gói hiển thị."]
    lines += ["", "Xanh24 Maps for Life"]
    message.set_content("\n".join(lines))
    if os.environ.get("CMS_MAIL_MODE") == "outbox":
        folder = Path(DATA_DIR) / "cms-mail-outbox"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"application-{row['id']}-{now()}-{secrets.token_hex(3)}.eml").write_text(message.as_string(), encoding="utf-8")
        return
    host = os.environ["CMS_SMTP_HOST"]
    port = int(os.environ.get("CMS_SMTP_PORT", "587"))
    if port == 465:
        session = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
    else:
        session = smtplib.SMTP(host, port, timeout=20)
    with session:
        if port != 465:
            session.starttls(context=ssl.create_default_context())
        session.login(os.environ["CMS_SMTP_USER"], os.environ["CMS_SMTP_PASSWORD"])
        session.send_message(message)


def send_and_record(application_id, password=None):
    row = q("SELECT a.*, c.username FROM cms_applications a LEFT JOIN cms_accounts c ON c.id=a.account_id WHERE a.id=?",
            (application_id,), one=True)
    try:
        deliver(row, password)
    except (OSError, smtplib.SMTPException, ValueError, KeyError) as exc:
        ex("UPDATE cms_applications SET email_status='failed',email_error=? WHERE id=?", (str(exc)[:500], application_id))
        return False
    ex("UPDATE cms_applications SET email_status='sent',email_error='',emailed_at=? WHERE id=?", (now(), application_id))
    return True


def in_registration_scope(ward):
    return role("S0") or bool(ward and ward in json.loads(g.cms_user["wards"] or "[]"))


def is_partner(row):
    return str(row["source_id"] or "").startswith("partner:")


def can_view_application(row):
    if role("S0"):
        return True
    if role("AREA"):
        return is_partner(row) and in_registration_scope(row["ward_slug"])
    return role("REVIEW") and not is_partner(row) and in_registration_scope(row["ward_slug"])


def managed_wards():
    assigned = set()
    for manager in q("SELECT wards FROM cms_accounts WHERE role='AREA' AND active=1"):
        try:
            assigned.update(json.loads(manager["wards"] or "[]"))
        except (TypeError, ValueError):
            continue
    return assigned


@applications.route("/api/cms/partner-registration/options")
def partner_options():
    assigned = managed_wards()
    wards = [dict(row) for row in q("SELECT slug,name FROM wards WHERE published=1 ORDER BY name")
             if row["slug"] in assigned]
    categories = [dict(row) for row in q("SELECT id,name FROM categories WHERE active=1 ORDER BY sort,name")]
    return jsonify(wards=wards, categories=categories)


def remove_private_files(paths):
    for path in paths:
        if IS_PG:
            ex("DELETE FROM media_files WHERE path=?", (path,))
        else:
            (Path(DATA_DIR) / path).unlink(missing_ok=True)


@applications.route("/api/cms/partner-registration", methods=["POST"])
def submit_partner_registration():
    if request.content_length and request.content_length > MAX_APPLICATION_BYTES:
        return error("Tổng dung lượng hồ sơ vượt quá 45 MB", 413)
    form = request.form
    owner_name = str(form.get("owner_name") or "").strip()
    email = str(form.get("email") or "").strip().lower()
    phone = str(form.get("phone") or "").strip()
    representative_role = str(form.get("representative_role") or "").strip()
    business_name = str(form.get("business_name") or "").strip()
    category = str(form.get("category") or "").strip()
    ward = str(form.get("ward_slug") or "").strip()
    address = str(form.get("address") or "").strip()
    opening_days = list(dict.fromkeys(form.getlist("opening_days")))
    opening_time = str(form.get("opening_time") or "").strip()
    closing_time = str(form.get("closing_time") or "").strip()
    files = request.files.getlist("documents")
    if not owner_name or len(owner_name) > 150 or not EMAIL_PATTERN.fullmatch(email) or len(email) > 200:
        return error("Cần họ tên người đại diện và email hợp lệ")
    if not PHONE_PATTERN.fullmatch(phone) or not 9 <= len(re.sub(r"\D", "", phone)) <= 15:
        return error("Số điện thoại không hợp lệ")
    if representative_role not in PARTNER_ROLES:
        return error("Cần chọn vai trò của người đại diện")
    if not business_name or len(business_name) > 200 or not address or len(address) > 500:
        return error("Cần tên thương hiệu và địa chỉ đầy đủ")
    if not q("SELECT 1 FROM categories WHERE id=? AND active=1", (category,), one=True):
        return error("Danh mục không hợp lệ")
    if ward not in managed_wards() or not q("SELECT 1 FROM wards WHERE slug=? AND published=1", (ward,), one=True):
        return error("Khu vực chưa có người quản lý phụ trách")
    if not opening_days or any(day not in WEEKDAYS for day in opening_days):
        return error("Cần chọn ngày mở cửa")
    if not all(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) for value in (opening_time, closing_time)):
        return error("Giờ mở cửa hoặc đóng cửa không hợp lệ")
    if not 1 <= len(files) <= MAX_DOCUMENTS:
        return error("Cần tải từ 1 đến 8 giấy tờ liên quan")

    documents = []
    total_bytes = 0
    token = secrets.token_hex(12)
    for upload in files:
        filename = str(upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()[:180]
        ext = Path(filename).suffix.lower()
        if not filename or ext not in DOCUMENT_TYPES:
            return error("Chỉ hỗ trợ PDF, DOC, DOCX, JPG, PNG hoặc WEBP")
        content = upload.stream.read(MAX_DOCUMENT_BYTES + 1)
        if not content or len(content) > MAX_DOCUMENT_BYTES:
            return error("Mỗi giấy tờ phải có nội dung và không quá 10 MB", 413)
        mime, signature = DOCUMENT_TYPES[ext]
        if not content.startswith(signature) or (ext == ".webp" and content[8:12] != b"WEBP"):
            return error("Nội dung giấy tờ không khớp định dạng tệp")
        total_bytes += len(content)
        if total_bytes > 40 * 1024 * 1024:
            return error("Tổng dung lượng giấy tờ vượt quá 40 MB", 413)
        path = f"cms-application-documents/{token}/{secrets.token_hex(12)}{ext}"
        documents.append({"name": filename, "path": path, "size": len(content), "mime": mime, "content": content})

    paths = []
    try:
        for document in documents:
            path = document["path"]
            if IS_PG:
                store_media(path, document["content"], document["mime"])
            else:
                target = Path(DATA_DIR) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(document["content"])
            paths.append(path)
        answers = {
            "representative_role": representative_role, "category": category,
            "opening_days": opening_days, "opening_time": opening_time, "closing_time": closing_time,
            "documents": [{key: value for key, value in document.items() if key != "content"} for document in documents],
        }
        aid = ex("INSERT INTO cms_applications(source_id,answers,email,owner_name,business_name,phone,address,ward_slug,submitted_at,created_at) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (f"partner:{token}", json.dumps(answers, ensure_ascii=False), email, owner_name,
                  business_name, phone, address, ward, now(), now()))
    except Exception:
        remove_private_files(paths)
        raise
    return jsonify(ok=True, id=aid, status="pending"), 201


def save_application(body):
    if not isinstance(body, dict):
        raise ValueError("Hồ sơ không hợp lệ")
    source_id = str(body.get("source_id") or "").strip()[:200]
    answers = body.get("answers") or {}
    if not source_id or not isinstance(answers, dict) or len(answers) > 80:
        raise ValueError("Hồ sơ không hợp lệ")
    serialized = json.dumps(answers, ensure_ascii=False, default=str)
    if len(serialized) > 50000:
        raise ValueError("Hồ sơ quá lớn")
    ward = registration_ward_slug(body.get("ward") or answers.get("Phường"))
    form_address = str(body.get("address") or answers.get("Nhập địa chỉ Chi tiết") or "").strip()[:500]
    existing = q("SELECT id,status,ward_slug,address FROM cms_applications WHERE source_id=?", (source_id,), one=True)
    if existing:
        if existing["status"] == "pending":
            if ward and not existing["ward_slug"]:
                ex("UPDATE cms_applications SET ward_slug=? WHERE id=?", (ward, existing["id"]))
            if form_address and not existing["address"]:
                ex("UPDATE cms_applications SET address=? WHERE id=?", (form_address, existing["id"]))
        return existing["id"], True
    try:
        submitted_at = int(body.get("submitted_at") or now())
    except (TypeError, ValueError):
        submitted_at = now()
    fields = [str(body.get(key) or "").strip()[:limit] for key, limit in
              (("email", 200), ("owner_name", 150), ("business_name", 200),
               ("tax_id", 80), ("license_file", 500), ("phone", 40))]
    aid = ex("INSERT INTO cms_applications(source_id,answers,email,owner_name,business_name,tax_id,license_file,phone,address,ward_slug,submitted_at,created_at) "
             "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
             (source_id, serialized, *fields, form_address, ward, submitted_at, now()))
    return aid, False


@applications.route("/api/cms/applications/intake", methods=["POST"])
def intake():
    expected = os.environ.get("CMS_FORMS_WEBHOOK_SECRET", "")
    supplied = request.headers.get("X-CMS-Webhook-Secret", "")
    if not expected:
        return error("Chưa cấu hình kết nối Google Form", 503)
    if not hmac.compare_digest(supplied, expected):
        return error("Không có quyền", 401)
    if request.content_length and request.content_length > 65536:
        return error("Hồ sơ quá lớn", 413)
    try:
        aid, duplicate = save_application(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error(str(exc))
    return jsonify(ok=True, id=aid, duplicate=duplicate)


@applications.route("/api/cms/applications/sync", methods=["POST"])
@authenticate
def sync_applications():
    if not role("S0"):
        return error("Chỉ Admin được đồng bộ Google Form", 403)
    url = os.environ.get("CMS_FORMS_PULL_URL", "")
    secret = os.environ.get("CMS_FORMS_PULL_SECRET", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "script.google.com" or not secret:
        return error("Chưa cấu hình URL Apps Script và khóa đồng bộ", 503)
    created = duplicate = 0
    try:
        for offset in range(0, 10000, 100):
            payload = json.dumps({"secret": secret, "offset": offset, "limit": 100}).encode("utf-8")
            with urlopen(Request(url, data=payload, headers={"Content-Type": "application/json"}), timeout=30) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Phản hồi Google Form quá lớn")
            result = json.loads(raw)
            items = result.get("items")
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError("Phản hồi Google Form không hợp lệ")
            for item in items:
                _, exists = save_application(item)
                duplicate += int(exists)
                created += int(not exists)
            if len(items) < 100:
                break
        else:
            raise ValueError("Form có quá 10.000 hồ sơ; cần đồng bộ theo lô")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return error("Không đồng bộ được Google Form; kiểm tra URL, khóa và quyền triển khai Apps Script", 502)
    return jsonify(ok=True, created=created, duplicate=duplicate)


@applications.route("/api/cms/applications")
@authenticate
def list_applications():
    if not role("S0", "REVIEW", "AREA"):
        return error("Không có quyền", 403)
    rows = q("SELECT * FROM cms_applications ORDER BY submitted_at DESC,id DESC")
    return jsonify(items=[public(row) for row in rows if can_view_application(row)])


@applications.route("/api/cms/applications/<int:aid>/files/<int:index>")
@authenticate
def application_file(aid, index):
    if not role("S0", "REVIEW", "AREA"):
        return error("Không có quyền", 403)
    row = q("SELECT * FROM cms_applications WHERE id=?", (aid,), one=True)
    if not row or not can_view_application(row) or not is_partner(row):
        return error("Không tìm thấy giấy tờ", 404)
    documents = json.loads(row["answers"] or "{}").get("documents") or []
    if not 0 <= index < len(documents):
        return error("Không tìm thấy giấy tờ", 404)
    document = documents[index]
    path = document.get("path")
    if not isinstance(path, str) or not path.startswith("cms-application-documents/"):
        return error("Không tìm thấy giấy tờ", 404)
    if IS_PG:
        stored = load_media(path)
        content = stored[1] if stored else None
    else:
        target = Path(DATA_DIR) / path
        content = target.read_bytes() if target.is_file() else None
    if content is None:
        return error("Không tìm thấy giấy tờ", 404)
    return send_file(io.BytesIO(content), mimetype=document.get("mime") or "application/octet-stream",
                     as_attachment=True, download_name=document.get("name") or "giay-to")


@applications.route("/api/cms/applications/<int:aid>/assign", methods=["POST"])
@authenticate
def assign_application(aid):
    if not role("S0"):
        return error("Chỉ quản trị hệ thống được phân phường", 403)
    ward = registration_ward_slug((request.get_json(silent=True) or {}).get("ward"))
    if not ward:
        return error("Phường không hợp lệ")
    connection = connect()
    try:
        connection.execute("BEGIN" if IS_PG else "BEGIN IMMEDIATE")
        row = connection.execute("SELECT status,source_id FROM cms_applications WHERE id=?" + (" FOR UPDATE" if IS_PG else ""), (aid,)).fetchone()
        if not row or row["status"] != "pending":
            connection.execute("ROLLBACK")
            return error("Hồ sơ không còn chờ phân công", 404)
        if is_partner(row):
            connection.execute("ROLLBACK")
            return error("Hồ sơ đối tác đã được gửi theo khu vực đăng ký", 409)
        connection.execute("UPDATE cms_applications SET ward_slug=? WHERE id=?", (ward, aid))
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    return jsonify(ok=True, ward_slug=ward)


def create_approved_account(aid, row, name, address, email, lat, lng, category, note,
                            requested_username=None, requested_password=None):
    """Create account, fixed pin and assignment as one database transaction."""
    from app import ward_for

    ward = ward_for(lat, lng)
    if ward != row["ward_slug"]:
        raise ValueError("Tọa độ ghim không thuộc phường đăng kí hoặc phường chưa có ranh giới bản đồ")
    answers = json.loads(row["answers"] or "{}") if is_partner(row) else {}
    days = answers.get("opening_days") or []
    day_names = {"mon": "T2", "tue": "T3", "wed": "T4", "thu": "T5", "fri": "T6", "sat": "T7", "sun": "CN"}
    hours = (f"{', '.join(day_names[day] for day in days if day in day_names)} "
             f"{answers.get('opening_time', '')}–{answers.get('closing_time', '')}").strip() if days else ""
    password = requested_password if is_partner(row) else secrets.token_urlsafe(12) + "Aa1!"
    username = requested_username if is_partner(row) else f"ghim_{aid}"
    connection = connect()
    try:
        connection.execute("BEGIN" if IS_PG else "BEGIN IMMEDIATE")
        current = connection.execute("SELECT status,ward_slug FROM cms_applications WHERE id=?" + (" FOR UPDATE" if IS_PG else ""), (aid,)).fetchone()
        if not current or current["status"] != "pending" or current["ward_slug"] != row["ward_slug"]:
            raise ValueError("Hồ sơ đã được xử lý hoặc đổi phường")
        if is_partner(row):
            if connection.execute("SELECT 1 FROM cms_accounts WHERE lower(username)=?", (username,)).fetchone() or connection.execute(
                "SELECT 1 FROM users WHERE lower(username)=?", (username,)).fetchone():
                raise ValueError("Tên đăng nhập đã tồn tại")
        else:
            while connection.execute("SELECT 1 FROM cms_accounts WHERE username=?", (username,)).fetchone() or connection.execute(
                "SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                username = f"ghim_{aid}_{secrets.token_hex(3)}"
        uid = connection.execute(
            "INSERT INTO cms_accounts(username,password_hash,full_name,email,phone,role,wards,active,read_only,created_by,created_at) "
            "VALUES(?,?,?,?,?,'OWNER',?,1,0,?,?)",
            (username, hash_password(password), row["owner_name"] or name, email, row["phone"],
             json.dumps([ward]), None if role("S0") else g.cms_user["id"], now()),
        ).lastrowid
        pid = connection.execute(
            "INSERT INTO pois(name,category,address,phone,hours,lat,lng,ward_slug,status,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,'published',?,?)",
            (name, category, address, row["phone"] or "", hours, lat, lng, ward, now(), now()),
        ).lastrowid
        connection.execute("UPDATE pois SET code=? WHERE id=?", (f"X24-{pid:05d}", pid))
        connection.execute("INSERT INTO cms_pins(poi_id,active,managed_by,created_at) VALUES(?,1,?,?)",
                           (pid, None if role("S0") else g.cms_user["id"], now()))
        connection.execute("INSERT INTO cms_assignments(account_id,poi_id,assigned_at) VALUES(?,?,?)", (uid, pid, now()))
        connection.execute(
            "UPDATE cms_applications SET status='approved',email=?,business_name=?,address=?,review_note=?,"
            "reviewed_by=?,reviewed_at=?,account_id=?,poi_id=?,ward_slug=?,email_status='pending' WHERE id=?",
            (email, name, address, note, g.cms_user["username"], now(), uid, pid, ward, aid),
        )
        connection.execute("COMMIT")
        return password
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def record_rejection(aid, ward, email, note):
    connection = connect()
    try:
        connection.execute("BEGIN" if IS_PG else "BEGIN IMMEDIATE")
        current = connection.execute("SELECT status,ward_slug FROM cms_applications WHERE id=?" + (" FOR UPDATE" if IS_PG else ""), (aid,)).fetchone()
        if not current or current["status"] != "pending" or current["ward_slug"] != ward:
            raise ValueError("Hồ sơ đã được xử lý hoặc đổi phường")
        connection.execute("UPDATE cms_applications SET status='rejected',email=?,review_note=?,reviewed_by=?,reviewed_at=?,email_status='pending' WHERE id=?",
                           (email, note, g.cms_user["username"], now(), aid))
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


@applications.route("/api/cms/applications/<int:aid>/review", methods=["POST"])
@authenticate
def review_application(aid):
    if not role("S0", "REVIEW", "AREA"):
        return error("Không có quyền", 403)
    row = q("SELECT * FROM cms_applications WHERE id=?", (aid,), one=True)
    if not row or not can_view_application(row):
        return error("Không tìm thấy hồ sơ trong khu vực", 404)
    if row["status"] != "pending":
        return error("Hồ sơ đã được xử lý", 409)
    if not row["ward_slug"]:
        return error("Cần phân phường trước khi kiểm duyệt")
    if not mail_ready():
        return error("Chưa cấu hình Gmail SMTP và URL đăng nhập CMS", 503)
    body = request.get_json(silent=True) or {}
    action = body.get("action")
    note = str(body.get("note") or "").strip()[:1000]
    if not note:
        return error("Cần nhập kết quả kiểm duyệt hoặc lý do từ chối")
    email = str(body.get("email") or row["email"]).strip()[:200]
    if not EMAIL_PATTERN.fullmatch(email):
        return error("Email người đăng kí không hợp lệ")
    if action == "reject":
        try:
            record_rejection(aid, row["ward_slug"], email, note)
        except ValueError as exc:
            return error(str(exc), 409)
        sent = send_and_record(aid)
        return jsonify(ok=True, status="rejected", email_status="sent" if sent else "failed")
    if action != "approve":
        return error("Thao tác không hợp lệ")
    name = str(body.get("business_name") or row["business_name"]).strip()[:200]
    address = str(body.get("address") or row["address"]).strip()[:500]
    category = str(body.get("category") or "").strip()
    if not name or not address or not q("SELECT 1 FROM categories WHERE id=?", (category,), one=True):
        return error("Cần tên doanh nghiệp, địa chỉ và danh mục ghim hợp lệ")
    try:
        lat, lng = float(body["lat"]), float(body["lng"])
    except (KeyError, TypeError, ValueError):
        return error("Cần nhập tọa độ ghim")
    if not (8 <= lat <= 24 and 102 <= lng <= 110):
        return error("Tọa độ ngoài phạm vi Việt Nam")
    username = password = None
    if is_partner(row):
        username = str(body.get("username") or "").strip().lower()
        password = str(body.get("password") or "")
        if not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
            return error("Tên đăng nhập phải có 3–40 ký tự a-z, 0-9, . _ -")
        problem = password_problem(password)
        if problem:
            return error(problem)
    try:
        password = create_approved_account(aid, row, name, address, email, lat, lng, category, note,
                                           username, password)
    except ValueError as exc:
        return error(str(exc), 409)
    sent = send_and_record(aid, password)
    return jsonify(ok=True, status="approved", email_status="sent" if sent else "failed")


@applications.route("/api/cms/applications/<int:aid>/resend", methods=["POST"])
@authenticate
def resend_application(aid):
    if not role("S0", "REVIEW", "AREA"):
        return error("Không có quyền", 403)
    row = q("SELECT * FROM cms_applications WHERE id=?", (aid,), one=True)
    if not row or not can_view_application(row):
        return error("Không tìm thấy hồ sơ trong khu vực", 404)
    if row["status"] == "pending" or row["email_status"] == "sent":
        return error("Hồ sơ chưa xử lý hoặc email đã gửi", 409)
    if not mail_ready():
        return error("Chưa cấu hình Gmail SMTP và URL đăng nhập CMS", 503)
    password = None
    if row["status"] == "approved":
        password = secrets.token_urlsafe(12) + "Aa1!"
        ex("UPDATE cms_accounts SET password_hash=? WHERE id=?", (hash_password(password), row["account_id"]))
    sent = send_and_record(aid, password)
    return jsonify(ok=True, email_status="sent" if sent else "failed")
