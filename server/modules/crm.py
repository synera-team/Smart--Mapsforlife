"""Xanh24 CRM — trung tâm quản lý khách hàng & vận hành cho www.xanh24.com.

Module máy chủ (không sửa mã lõi). Giao diện: /crm/ (web/crm/), ứng dụng Android "Xanh24 CRM" (android-crm/).

Quản lý:
  * Khách hàng: nhà quảng cáo, đối tác địa điểm/voucher, chủ điểm đặt kiosk, khách tiềm năng — theo phễu bán hàng.
  * Hợp đồng (quảng cáo, mặt bằng, đối tác) + các lần thanh toán → doanh thu, công nợ, hợp đồng sắp hết hạn.
  * Hoạt động & việc cần làm (gọi điện, gặp, bảo trì màn hình…) có người phụ trách, hạn xử lý.
  * Kết nối dữ liệu sẵn có của xanh24.com: màn hình kiosk (trực tuyến/mất kết nối), quảng cáo, địa điểm,
    lượt hiển thị quảng cáo (sự kiện ad_impression) → báo cáo cho nhà quảng cáo, xuất CSV.

Quyền (thêm vào ma trận quyền chung):
  crm.read   CW — xem CRM          crm.edit   CW — thêm/sửa khách hàng, hoạt động
  crm.finance S1 — hợp đồng, thanh toán   crm.delete S1 — xoá dữ liệu CRM
"""
import calendar
import csv
import io
import json
import os
import time

from flask import Response, g, jsonify, request, send_from_directory

KEY = "crm"
P = f"/api/modules/{KEY}"
DAY = 86400
TZ = 7 * 3600  # giờ Việt Nam

KINDS = {"advertiser": "Nhà quảng cáo", "partner": "Đối tác địa điểm / voucher", "site_owner": "Chủ điểm đặt kiosk", "other": "Khác"}
STAGES = {"lead": "Tiềm năng", "contacted": "Đã liên hệ", "quoted": "Đã báo giá", "negotiating": "Đàm phán",
          "won": "Đã ký / Đang hợp tác", "lost": "Không thành"}
CONTRACT_KINDS = {"ads": "Quảng cáo trên kiosk", "placement": "Thuê mặt bằng đặt kiosk", "partner": "Đối tác địa điểm / voucher",
                  "service": "Dịch vụ khác"}
CONTRACT_STATUS = {"draft": "Nháp", "active": "Hiệu lực", "ended": "Đã kết thúc", "cancelled": "Đã huỷ"}
ACT_KINDS = {"note": "Ghi chú", "call": "Gọi điện", "meeting": "Gặp mặt", "email": "Email", "visit": "Khảo sát / đến điểm",
             "task": "Việc cần làm", "maintenance": "Bảo trì màn hình"}

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS mod_crm_customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT DEFAULT 'advertiser', stage TEXT DEFAULT 'lead',
        tax_code TEXT DEFAULT '', contact_name TEXT DEFAULT '', phone TEXT DEFAULT '', email TEXT DEFAULT '',
        address TEXT DEFAULT '', ward_slug TEXT DEFAULT '', source TEXT DEFAULT '', owner_id INTEGER,
        expected_value INTEGER DEFAULT 0, tags TEXT DEFAULT '[]', poi_ids TEXT DEFAULT '[]', notes TEXT DEFAULT '',
        created_by INTEGER, created_at INTEGER, updated_at INTEGER)""",
    """CREATE TABLE IF NOT EXISTS mod_crm_contracts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, code TEXT DEFAULT '', kind TEXT DEFAULT 'ads',
        title TEXT DEFAULT '', value INTEGER DEFAULT 0, start_at INTEGER, end_at INTEGER, status TEXT DEFAULT 'draft',
        ad_ids TEXT DEFAULT '[]', device_codes TEXT DEFAULT '[]', notes TEXT DEFAULT '',
        created_by INTEGER, created_at INTEGER, updated_at INTEGER)""",
    """CREATE TABLE IF NOT EXISTS mod_crm_payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, amount INTEGER DEFAULT 0, paid_at INTEGER,
        method TEXT DEFAULT '', note TEXT DEFAULT '', created_by INTEGER, created_at INTEGER)""",
    """CREATE TABLE IF NOT EXISTS mod_crm_activities(
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, contract_id INTEGER, device_code TEXT DEFAULT '',
        kind TEXT DEFAULT 'note', title TEXT DEFAULT '', content TEXT DEFAULT '', due_at INTEGER, done INTEGER DEFAULT 0,
        done_at INTEGER, assignee_id INTEGER, created_by INTEGER, created_at INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_crm_ct_customer ON mod_crm_contracts(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_crm_pay_contract ON mod_crm_payments(contract_id)",
    "CREATE INDEX IF NOT EXISTS idx_crm_act_customer ON mod_crm_activities(customer_id)",
]

CUST_FIELDS = ["name", "kind", "stage", "tax_code", "contact_name", "phone", "email", "address", "ward_slug", "source",
               "owner_id", "expected_value", "tags", "poi_ids", "notes"]
CT_FIELDS = ["customer_id", "code", "kind", "title", "value", "start_at", "end_at", "status", "ad_ids", "device_codes", "notes"]
ACT_FIELDS = ["customer_id", "contract_id", "device_code", "kind", "title", "content", "due_at", "assignee_id"]
JSON_FIELDS = {"tags", "poi_ids", "ad_ids", "device_codes"}
INT_FIELDS = {"owner_id", "expected_value", "customer_id", "contract_id", "value", "start_at", "end_at", "due_at", "assignee_id"}


def now():
    return int(time.time())


def day_start(t=None):
    t = now() if t is None else t
    return ((t + TZ) // DAY) * DAY - TZ


def day_key(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t + TZ))


def register(app, ctx):
    import auth
    for p, r in {"crm.read": "CW", "crm.edit": "CW", "crm.finance": "S1", "crm.delete": "S1"}.items():
        auth.PERMISSIONS.setdefault(p, r)
    for s in SCHEMA:
        ctx.ex(s)

    q, ex, require, audit = ctx.q, ctx.ex, ctx.require, ctx.audit

    import db as _db
    crm_dir = os.path.join(_db.BASE_DIR, "web", "crm")

    @app.route("/crm", endpoint="mod_crm_page_noslash")
    @app.route("/crm/", endpoint="mod_crm_page")
    def crm_page():
        """Trang CRM (giao diện tĩnh web/crm/) — phục vụ trực tiếp, không phụ thuộc thư mục web giao diện chính."""
        resp = send_from_directory(crm_dir, "index.html", max_age=0)
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp

    @app.route("/crm/<path:fn>", endpoint="mod_crm_static")
    def crm_static(fn):
        resp = send_from_directory(crm_dir, fn, max_age=0)
        if fn == "sw.js":
            resp.headers["Service-Worker-Allowed"] = "/crm/"
        return resp

    # ------------------------------------------------------------------ helpers
    def err(msg, code=400):
        return jsonify(error=msg), code

    def body():
        return request.get_json(silent=True) or {}

    def jl(v):
        try:
            x = json.loads(v or "[]")
            return x if isinstance(x, list) else []
        except Exception:
            return []

    def row(r):
        d = dict(r)
        for k in JSON_FIELDS:
            if k in d:
                d[k] = jl(d[k])
        return d

    def clean(d, fields):
        out = {}
        for k in fields:
            if k not in d:
                continue
            v = d[k]
            if k in JSON_FIELDS:
                v = json.dumps([x for x in (v if isinstance(v, list) else []) if x not in (None, "")][:200], ensure_ascii=False)
            elif k in INT_FIELDS:
                try:
                    v = int(float(v)) if v not in (None, "") else None
                except (TypeError, ValueError):
                    v = None
            else:
                v = str(v if v is not None else "").strip()[:4000]
            out[k] = v
        return out

    def insert(table, data):
        cols = list(data)
        return ex(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [data[c] for c in cols])

    def update(table, rid, data):
        if data:
            ex(f"UPDATE {table} SET {','.join(k + '=?' for k in data)} WHERE id=?", [*data.values(), rid])

    def users_map():
        return {r["id"]: (r["full_name"] or r["username"]) for r in q("SELECT id, username, full_name FROM users")}

    def paid_map(ids=None):
        rows = q("SELECT contract_id, SUM(amount) s FROM mod_crm_payments GROUP BY contract_id")
        return {r["contract_id"]: int(r["s"] or 0) for r in rows}

    def contract_out(r, paid, cust=None):
        d = row(r)
        d["paid"] = paid.get(d["id"], 0)
        d["due"] = max(0, int(d["value"] or 0) - d["paid"])
        t = now()
        d["expiring"] = bool(d["status"] == "active" and d["end_at"] and t <= d["end_at"] <= t + 30 * DAY)
        d["expired"] = bool(d["status"] == "active" and d["end_at"] and d["end_at"] < t)
        if cust is not None:
            d["customer_name"] = cust.get(d["customer_id"], "")
        return d

    def impressions_by_ad(since, until=None, devices=None):
        """Đếm lượt hiển thị quảng cáo theo mã quảng cáo (gộp bằng SQL theo chuỗi data để nhẹ máy chủ)."""
        until = until or now() + 60
        sql = "SELECT data, device_code, COUNT(*) n FROM events WHERE type='ad_impression' AND at>=? AND at<?"
        args = [since, until]
        if devices:
            sql += f" AND device_code IN ({','.join('?' * len(devices))})"
            args += list(devices)
        out = {}
        for r in q(sql + " GROUP BY data, device_code", tuple(args)):
            try:
                aid = int(json.loads(r["data"] or "{}").get("ad"))
            except Exception:
                continue
            out[aid] = out.get(aid, 0) + int(r["n"])
        return out

    # ------------------------------------------------------------------ meta / phiên
    @app.route(f"{P}/meta", endpoint="mod_crm_meta")
    @require("crm.read")
    def meta():
        u = g.user
        return jsonify(kinds=KINDS, stages=STAGES, contract_kinds=CONTRACT_KINDS, contract_status=CONTRACT_STATUS, act_kinds=ACT_KINDS,
                       users=[{"id": r["id"], "name": r["full_name"] or r["username"], "role": r["role"]}
                              for r in q("SELECT id, username, full_name, role FROM users WHERE active=1 ORDER BY username")],
                       wards=[{"slug": r["slug"], "name": r["name"]} for r in q("SELECT slug, name FROM wards ORDER BY name")],
                       devices=[{"code": r["code"], "name": r["name"]} for r in q("SELECT code, name FROM devices ORDER BY code")],
                       ads=[{"id": r["id"], "title": r["title"], "status": r["status"]} for r in q("SELECT id, title, status FROM ads ORDER BY id DESC LIMIT 500")],
                       me={"id": u["id"], "role": u["role"]})

    @app.route(f"{P}/refresh", methods=["POST"], endpoint="mod_crm_refresh")
    @require("crm.read")
    def refresh():
        """Gia hạn phiên cho màn hình CRM treo tường (đang dùng thì không bị đăng xuất giữa chừng)."""
        if not g.user["id"]:
            return err("API key không gia hạn được", 403)
        return jsonify(token=auth.issue_token(g.user), user=auth.public_user(g.user))

    @app.route(f"{P}/pois", endpoint="mod_crm_pois")
    @require("crm.read")
    def pois_lookup():
        s = f"%{(request.args.get('q') or '').strip().lower()}%"
        rows = q("SELECT id, name, ward_slug, status FROM pois WHERE lower(name) LIKE ? ORDER BY name LIMIT 30", (s,))
        return jsonify(items=[dict(r) for r in rows])

    # ------------------------------------------------------------------ tổng quan
    @app.route(f"{P}/overview", endpoint="mod_crm_overview")
    @require("crm.read")
    def overview():
        t = now()
        d0 = day_start(t)
        since = d0 - 29 * DAY
        days = {day_key(d0 - i * DAY): {"day": day_key(d0 - i * DAY), "sessions": 0, "impressions": 0, "poi_views": 0, "routes": 0}
                for i in range(29, -1, -1)}
        key_of = {"session_start": "sessions", "ad_impression": "impressions", "poi_view": "poi_views", "route_request": "routes"}
        for r in q("""SELECT ((at + ?) / 86400) d, type, COUNT(*) n FROM events WHERE at>=? AND type IN
                      ('session_start','ad_impression','poi_view','route_request') GROUP BY d, type""", (TZ, since)):
            k = time.strftime("%Y-%m-%d", time.gmtime(int(r["d"]) * DAY))
            if k in days:
                days[k][key_of[r["type"]]] += int(r["n"])
        series = list(days.values())
        today = series[-1]

        devs = [dict(r) for r in q("SELECT code, name, ward_slug, address, last_seen, active FROM devices ORDER BY code")]
        for d in devs:
            d["online"] = bool(d["last_seen"] and t - d["last_seen"] < 180)
        active_devs = [d for d in devs if d["active"]]

        paid = paid_map()
        cust = {r["id"]: r["name"] for r in q("SELECT id, name FROM mod_crm_customers")}
        cts = [contract_out(r, paid, cust) for r in q("SELECT * FROM mod_crm_contracts")]
        active = [c for c in cts if c["status"] == "active"]
        m0 = time.gmtime(t + TZ)
        month_start = calendar.timegm((m0.tm_year, m0.tm_mon, 1, 0, 0, 0)) - TZ
        month_paid = q("SELECT SUM(amount) s FROM mod_crm_payments WHERE paid_at>=?", (month_start,), one=True)
        rev = []
        for i in range(5, -1, -1):
            y, mth = m0.tm_year, m0.tm_mon - i
            while mth <= 0:
                mth += 12; y -= 1
            a = calendar.timegm((y, mth, 1, 0, 0, 0)) - TZ
            y2, m2 = (y + 1, 1) if mth == 12 else (y, mth + 1)
            b = calendar.timegm((y2, m2, 1, 0, 0, 0)) - TZ
            s = q("SELECT SUM(amount) s FROM mod_crm_payments WHERE paid_at>=? AND paid_at<?", (a, b), one=True)
            rev.append({"month": f"{mth:02d}/{y}", "amount": int((s and s["s"]) or 0)})

        pipe = {k: {"stage": k, "label": v, "n": 0, "value": 0} for k, v in STAGES.items()}
        kinds = {k: 0 for k in KINDS}
        for r in q("SELECT stage, kind, expected_value FROM mod_crm_customers"):
            if r["stage"] in pipe:
                pipe[r["stage"]]["n"] += 1
                pipe[r["stage"]]["value"] += int(r["expected_value"] or 0)
            if r["kind"] in kinds:
                kinds[r["kind"]] += 1

        um = users_map()
        tasks = [dict(r) for r in q("""SELECT a.*, c.name customer_name FROM mod_crm_activities a LEFT JOIN mod_crm_customers c ON c.id=a.customer_id
                                       WHERE a.done=0 AND a.due_at IS NOT NULL AND a.due_at < ? ORDER BY a.due_at LIMIT 12""", (d0 + DAY,))]
        for x in tasks:
            x["assignee"] = um.get(x["assignee_id"], "")
            x["overdue"] = x["due_at"] < d0
        imp7 = impressions_by_ad(d0 - 6 * DAY)
        ad_titles = {r["id"]: r["title"] for r in q("SELECT id, title FROM ads")}
        top_ads = sorted(({"id": k, "title": ad_titles.get(k, f"#{k}"), "n": v} for k, v in imp7.items()), key=lambda x: -x["n"])[:6]

        return jsonify(
            server_time=t,
            today=today, days=series,
            kiosks={"total": len(active_devs), "online": sum(1 for d in active_devs if d["online"]),
                    "offline": [d for d in active_devs if not d["online"]][:20], "items": devs},
            approvals={"revisions": q("SELECT COUNT(*) n FROM revisions WHERE status='pending'", one=True)["n"],
                       "ads": q("SELECT COUNT(*) n FROM ads WHERE status='pending'", one=True)["n"]},
            content={"pois": q("SELECT COUNT(*) n FROM pois WHERE status='published'", one=True)["n"],
                     "ads_live": q("SELECT COUNT(*) n FROM ads WHERE status='published' AND (end_at IS NULL OR end_at>?)", (t,), one=True)["n"]},
            money={"month_paid": int((month_paid and month_paid["s"]) or 0),
                   "active_value": sum(int(c["value"] or 0) for c in active),
                   "receivable": sum(c["due"] for c in active if c["kind"] != "placement"),
                   "active_contracts": len(active), "revenue_6m": rev},
            expiring=sorted([c for c in cts if c["expiring"] or c["expired"]], key=lambda c: c["end_at"] or 0)[:10],
            pipeline=list(pipe.values()), customer_kinds=kinds,
            customers=q("SELECT COUNT(*) n FROM mod_crm_customers", one=True)["n"],
            tasks=tasks,
            tasks_open=q("SELECT COUNT(*) n FROM mod_crm_activities WHERE done=0 AND kind IN ('task','maintenance','call','meeting','visit') AND due_at IS NOT NULL", one=True)["n"],
            top_ads=top_ads,
        )

    # ------------------------------------------------------------------ khách hàng
    @app.route(f"{P}/customers", endpoint="mod_crm_customers")
    @require("crm.read")
    def customers():
        sql = "SELECT * FROM mod_crm_customers WHERE 1=1"
        args = []
        for k in ("kind", "stage", "ward_slug"):
            v = request.args.get(k)
            if v:
                sql += f" AND {k}=?"; args.append(v)
        s = (request.args.get("q") or "").strip().lower()
        if s:
            sql += " AND (lower(name) LIKE ? OR lower(contact_name) LIKE ? OR phone LIKE ? OR lower(email) LIKE ? OR tax_code LIKE ?)"
            args += [f"%{s}%"] * 5
        rows = [row(r) for r in q(sql + " ORDER BY updated_at DESC, id DESC LIMIT 1000", tuple(args))]
        paid = paid_map()
        agg = {}
        for c in q("SELECT id, customer_id, value, status FROM mod_crm_contracts"):
            a = agg.setdefault(c["customer_id"], {"contracts": 0, "active": 0, "value": 0, "paid": 0})
            a["contracts"] += 1
            if c["status"] == "active":
                a["active"] += 1
                a["value"] += int(c["value"] or 0)
                a["paid"] += paid.get(c["id"], 0)
        last = {r["customer_id"]: r["m"] for r in q("SELECT customer_id, MAX(created_at) m FROM mod_crm_activities GROUP BY customer_id")}
        um = users_map()
        for r in rows:
            r.update(agg.get(r["id"], {"contracts": 0, "active": 0, "value": 0, "paid": 0}))
            r["last_activity"] = last.get(r["id"])
            r["owner"] = um.get(r["owner_id"], "")
        return jsonify(items=rows)

    @app.route(f"{P}/customers/<int:cid>", endpoint="mod_crm_customer")
    @require("crm.read")
    def customer(cid):
        r = q("SELECT * FROM mod_crm_customers WHERE id=?", (cid,), one=True)
        if not r:
            return err("Không tìm thấy khách hàng", 404)
        c = row(r)
        paid = paid_map()
        cts = [contract_out(x, paid) for x in q("SELECT * FROM mod_crm_contracts WHERE customer_id=? ORDER BY start_at DESC, id DESC", (cid,))]
        for x in cts:
            x["payments"] = [dict(p) for p in q("SELECT * FROM mod_crm_payments WHERE contract_id=? ORDER BY paid_at DESC", (x["id"],))]
        um = users_map()
        acts = [dict(a) for a in q("SELECT * FROM mod_crm_activities WHERE customer_id=? ORDER BY COALESCE(due_at, created_at) DESC LIMIT 200", (cid,))]
        for a in acts:
            a["assignee"] = um.get(a["assignee_id"], "")
            a["author"] = um.get(a["created_by"], "")
        c["owner"] = um.get(c["owner_id"], "")
        ids = c["poi_ids"]
        c["pois"] = [dict(p) for p in q(f"SELECT id, name, ward_slug, status FROM pois WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))] if ids else []
        ad_ids = sorted({a for x in cts for a in x["ad_ids"]})
        imp = impressions_by_ad(day_start() - 29 * DAY)
        c["ads"] = [dict(a, impressions_30d=imp.get(a["id"], 0)) for a in
                    q(f"SELECT id, title, status, media_type, start_at, end_at FROM ads WHERE id IN ({','.join('?' * len(ad_ids))})", tuple(ad_ids))] if ad_ids else []
        return jsonify(customer=c, contracts=cts, activities=acts)

    @app.route(f"{P}/customers", methods=["POST"], endpoint="mod_crm_customer_new")
    @app.route(f"{P}/customers/<int:cid>", methods=["PUT"], endpoint="mod_crm_customer_save")
    @require("crm.edit")
    def customer_save(cid=None):
        d = clean(body(), CUST_FIELDS)
        if cid is None and not d.get("name"):
            return err("Thiếu tên khách hàng")
        if "name" in d and not d["name"]:
            return err("Tên khách hàng không được để trống")
        if d.get("kind") and d["kind"] not in KINDS:
            return err("Loại khách hàng không hợp lệ")
        if d.get("stage") and d["stage"] not in STAGES:
            return err("Giai đoạn không hợp lệ")
        d["updated_at"] = now()
        if cid is None:
            d.update(created_by=g.user["id"], created_at=now())
            d.setdefault("owner_id", g.user["id"] or None)
            cid = insert("mod_crm_customers", d)
            audit("crm.customer.create", "crm_customer", cid)
        else:
            old = q("SELECT stage FROM mod_crm_customers WHERE id=?", (cid,), one=True)
            if not old:
                return err("Không tìm thấy khách hàng", 404)
            update("mod_crm_customers", cid, d)
            if d.get("stage") and d["stage"] != old["stage"]:
                insert("mod_crm_activities", {"customer_id": cid, "kind": "note", "title": f"Chuyển giai đoạn: {STAGES.get(old['stage'], old['stage'])} → {STAGES[d['stage']]}",
                                              "done": 1, "created_by": g.user["id"], "created_at": now()})
            audit("crm.customer.update", "crm_customer", cid)
        ctx.fire_webhook("module.crm.customer", {"id": cid})
        return jsonify(ok=True, id=cid)

    @app.route(f"{P}/customers/<int:cid>", methods=["DELETE"], endpoint="mod_crm_customer_del")
    @require("crm.delete")
    def customer_delete(cid):
        for r in q("SELECT id FROM mod_crm_contracts WHERE customer_id=?", (cid,)):
            ex("DELETE FROM mod_crm_payments WHERE contract_id=?", (r["id"],))
        ex("DELETE FROM mod_crm_contracts WHERE customer_id=?", (cid,))
        ex("DELETE FROM mod_crm_activities WHERE customer_id=?", (cid,))
        ex("DELETE FROM mod_crm_customers WHERE id=?", (cid,))
        audit("crm.customer.delete", "crm_customer", cid)
        return jsonify(ok=True)

    # ------------------------------------------------------------------ hợp đồng & thanh toán
    @app.route(f"{P}/contracts", endpoint="mod_crm_contracts")
    @require("crm.read")
    def contracts():
        sql = "SELECT * FROM mod_crm_contracts WHERE 1=1"
        args = []
        for k in ("status", "kind", "customer_id"):
            v = request.args.get(k)
            if v:
                sql += f" AND {k}=?"; args.append(v)
        paid = paid_map()
        cust = {r["id"]: r["name"] for r in q("SELECT id, name FROM mod_crm_customers")}
        items = [contract_out(r, paid, cust) for r in q(sql + " ORDER BY COALESCE(end_at, 0) DESC, id DESC LIMIT 1000", tuple(args))]
        return jsonify(items=items)

    @app.route(f"{P}/contracts", methods=["POST"], endpoint="mod_crm_contract_new")
    @app.route(f"{P}/contracts/<int:kid>", methods=["PUT"], endpoint="mod_crm_contract_save")
    @require("crm.finance")
    def contract_save(kid=None):
        d = clean(body(), CT_FIELDS)
        if kid is None and not d.get("customer_id"):
            return err("Chọn khách hàng cho hợp đồng")
        if d.get("customer_id") and not q("SELECT 1 FROM mod_crm_customers WHERE id=?", (d["customer_id"],), one=True):
            return err("Khách hàng không tồn tại")
        if d.get("kind") and d["kind"] not in CONTRACT_KINDS:
            return err("Loại hợp đồng không hợp lệ")
        if d.get("status") and d["status"] not in CONTRACT_STATUS:
            return err("Trạng thái hợp đồng không hợp lệ")
        if d.get("start_at") and d.get("end_at") and d["end_at"] < d["start_at"]:
            return err("Ngày kết thúc phải sau ngày bắt đầu")
        if (d.get("value") or 0) < 0:
            return err("Giá trị hợp đồng không hợp lệ")
        d["updated_at"] = now()
        if kid is None:
            d.update(created_by=g.user["id"], created_at=now())
            if not d.get("code"):
                n = q("SELECT COUNT(*) n FROM mod_crm_contracts", one=True)["n"] + 1
                d["code"] = f"HD-{time.strftime('%Y', time.gmtime(now() + TZ))}-{n:04d}"
            kid = insert("mod_crm_contracts", d)
            cid = d["customer_id"]
            if d.get("status") == "active":
                ex("UPDATE mod_crm_customers SET stage='won', updated_at=? WHERE id=? AND stage!='won'", (now(), cid))
            audit("crm.contract.create", "crm_contract", kid)
        else:
            if not q("SELECT 1 FROM mod_crm_contracts WHERE id=?", (kid,), one=True):
                return err("Không tìm thấy hợp đồng", 404)
            update("mod_crm_contracts", kid, d)
            audit("crm.contract.update", "crm_contract", kid)
        return jsonify(ok=True, id=kid)

    @app.route(f"{P}/contracts/<int:kid>", methods=["DELETE"], endpoint="mod_crm_contract_del")
    @require("crm.delete")
    def contract_delete(kid):
        ex("DELETE FROM mod_crm_payments WHERE contract_id=?", (kid,))
        ex("DELETE FROM mod_crm_contracts WHERE id=?", (kid,))
        audit("crm.contract.delete", "crm_contract", kid)
        return jsonify(ok=True)

    @app.route(f"{P}/contracts/<int:kid>/payments", methods=["POST"], endpoint="mod_crm_payment_new")
    @require("crm.finance")
    def payment_add(kid):
        if not q("SELECT 1 FROM mod_crm_contracts WHERE id=?", (kid,), one=True):
            return err("Không tìm thấy hợp đồng", 404)
        d = body()
        try:
            amount = int(float(d.get("amount") or 0))
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            return err("Số tiền phải lớn hơn 0")
        try:
            paid_at = int(d.get("paid_at") or now())
        except (TypeError, ValueError):
            paid_at = now()
        pid = insert("mod_crm_payments", {"contract_id": kid, "amount": amount, "paid_at": paid_at,
                                          "method": str(d.get("method") or "")[:60], "note": str(d.get("note") or "")[:500],
                                          "created_by": g.user["id"], "created_at": now()})
        audit("crm.payment.create", "crm_contract", kid, {"amount": amount})
        return jsonify(ok=True, id=pid)

    @app.route(f"{P}/payments/<int:pid>", methods=["DELETE"], endpoint="mod_crm_payment_del")
    @require("crm.finance")
    def payment_delete(pid):
        ex("DELETE FROM mod_crm_payments WHERE id=?", (pid,))
        audit("crm.payment.delete", "crm_payment", pid)
        return jsonify(ok=True)

    # ------------------------------------------------------------------ hoạt động & việc cần làm
    @app.route(f"{P}/activities", endpoint="mod_crm_activities")
    @require("crm.read")
    def activities():
        sql = """SELECT a.*, c.name customer_name FROM mod_crm_activities a LEFT JOIN mod_crm_customers c ON c.id=a.customer_id WHERE 1=1"""
        args = []
        st = request.args.get("status", "open")
        if st == "open":
            sql += " AND a.done=0 AND a.due_at IS NOT NULL"
        elif st == "done":
            sql += " AND a.done=1 AND a.due_at IS NOT NULL"
        if request.args.get("mine") == "1":
            sql += " AND a.assignee_id=?"; args.append(g.user["id"])
        for k in ("customer_id", "device_code", "kind"):
            v = request.args.get(k)
            if v:
                sql += f" AND a.{k}=?"; args.append(v)
        order = " ORDER BY a.due_at ASC" if st == "open" else " ORDER BY COALESCE(a.done_at, a.created_at) DESC"
        um = users_map()
        items = [dict(r) for r in q(sql + order + " LIMIT 500", tuple(args))]
        d0 = day_start()
        for a in items:
            a["assignee"] = um.get(a["assignee_id"], "")
            a["author"] = um.get(a["created_by"], "")
            a["overdue"] = bool(not a["done"] and a["due_at"] and a["due_at"] < d0)
        return jsonify(items=items)

    @app.route(f"{P}/activities", methods=["POST"], endpoint="mod_crm_activity_new")
    @app.route(f"{P}/activities/<int:aid>", methods=["PUT"], endpoint="mod_crm_activity_save")
    @require("crm.edit")
    def activity_save(aid=None):
        d = clean(body(), ACT_FIELDS)
        if d.get("kind") and d["kind"] not in ACT_KINDS:
            return err("Loại hoạt động không hợp lệ")
        if aid is None:
            if not (d.get("title") or d.get("content")):
                return err("Nhập nội dung hoạt động")
            d.update(created_by=g.user["id"], created_at=now(), done=0)
            if not d.get("due_at"):
                d["done"] = 1  # ghi chú / nhật ký (không có hạn) → lưu như đã xong
            aid = insert("mod_crm_activities", d)
            if d.get("customer_id"):
                ex("UPDATE mod_crm_customers SET updated_at=? WHERE id=?", (now(), d["customer_id"]))
            audit("crm.activity.create", "crm_activity", aid)
        else:
            update("mod_crm_activities", aid, d)
            audit("crm.activity.update", "crm_activity", aid)
        return jsonify(ok=True, id=aid)

    @app.route(f"{P}/activities/<int:aid>/done", methods=["POST"], endpoint="mod_crm_activity_done")
    @require("crm.edit")
    def activity_done(aid):
        done = 0 if body().get("done") is False else 1
        ex("UPDATE mod_crm_activities SET done=?, done_at=? WHERE id=?", (done, now() if done else None, aid))
        audit("crm.activity.done", "crm_activity", aid, {"done": done})
        return jsonify(ok=True)

    @app.route(f"{P}/activities/<int:aid>", methods=["DELETE"], endpoint="mod_crm_activity_del")
    @require("crm.edit")
    def activity_delete(aid):
        a = q("SELECT created_by FROM mod_crm_activities WHERE id=?", (aid,), one=True)
        if a and a["created_by"] != g.user["id"] and not auth.has_perm(g.user, "crm.delete"):
            return err("Chỉ người tạo hoặc Admin S1 trở lên được xoá", 403)
        ex("DELETE FROM mod_crm_activities WHERE id=?", (aid,))
        return jsonify(ok=True)

    # ------------------------------------------------------------------ màn hình kiosk
    @app.route(f"{P}/devices", endpoint="mod_crm_devices")
    @require("crm.read")
    def devices():
        t = now()
        d0 = day_start(t)
        items = [dict(r) for r in q("""SELECT id, code, name, ward_slug, address, lat, lng, gps_lat, gps_lng, last_seen, last_ip, screen,
                                       user_agent, active, notes FROM devices ORDER BY code""")]
        cnt = {}
        for r in q("""SELECT device_code, type, COUNT(*) n FROM events WHERE at>=? AND type IN ('session_start','ad_impression','poi_view','route_request')
                      GROUP BY device_code, type""", (d0,)):
            cnt.setdefault(r["device_code"], {})[r["type"]] = int(r["n"])
        week = {r["device_code"]: int(r["n"]) for r in q("SELECT device_code, COUNT(*) n FROM events WHERE at>=? AND type='session_start' GROUP BY device_code", (d0 - 6 * DAY,))}
        contracts_by_dev = {}
        cust = {r["id"]: r["name"] for r in q("SELECT id, name FROM mod_crm_customers")}
        for c in q("SELECT id, code, customer_id, kind, device_codes, status, end_at FROM mod_crm_contracts WHERE status='active'"):
            for code in jl(c["device_codes"]):
                contracts_by_dev.setdefault(code, []).append({"id": c["id"], "code": c["code"], "kind": c["kind"], "end_at": c["end_at"],
                                                              "customer_id": c["customer_id"], "customer": cust.get(c["customer_id"], "")})
        open_tasks = {r["device_code"]: int(r["n"]) for r in q("SELECT device_code, COUNT(*) n FROM mod_crm_activities WHERE done=0 AND device_code!='' GROUP BY device_code")}
        for d in items:
            d["online"] = bool(d["last_seen"] and t - d["last_seen"] < 180)
            c = cnt.get(d["code"], {})
            d["today"] = {"sessions": c.get("session_start", 0), "impressions": c.get("ad_impression", 0),
                          "poi_views": c.get("poi_view", 0), "routes": c.get("route_request", 0)}
            d["sessions_7d"] = week.get(d["code"], 0)
            d["contracts"] = contracts_by_dev.get(d["code"], [])
            d["open_tasks"] = open_tasks.get(d["code"], 0)
        return jsonify(items=items, server_time=t)

    # ------------------------------------------------------------------ báo cáo quảng cáo
    @app.route(f"{P}/report", endpoint="mod_crm_report")
    @require("crm.read")
    def report():
        """Báo cáo lượt hiển thị quảng cáo theo hợp đồng/khách hàng, theo ngày và theo màn hình. ?format=csv để tải về."""
        t = now()
        try:
            frm = int(request.args.get("from") or day_start(t) - 29 * DAY)
            to = int(request.args.get("to") or t + 60)
        except ValueError:
            return err("Khoảng thời gian không hợp lệ")
        if to - frm > 400 * DAY:
            return err("Khoảng thời gian tối đa 400 ngày")
        ad_ids, devices_f, title = set(), None, "Tất cả quảng cáo"
        if request.args.get("contract"):
            c = q("SELECT * FROM mod_crm_contracts WHERE id=?", (request.args["contract"],), one=True)
            if not c:
                return err("Không tìm thấy hợp đồng", 404)
            ad_ids = set(jl(c["ad_ids"]))
            devices_f = jl(c["device_codes"]) or None
            title = f"Hợp đồng {c['code']}"
        elif request.args.get("customer"):
            for c in q("SELECT ad_ids FROM mod_crm_contracts WHERE customer_id=?", (request.args["customer"],)):
                ad_ids |= set(jl(c["ad_ids"]))
            cu = q("SELECT name FROM mod_crm_customers WHERE id=?", (request.args["customer"],), one=True)
            title = cu["name"] if cu else title
        elif request.args.get("ad"):
            ad_ids = {int(request.args["ad"])}
        sql = "SELECT data, device_code, ((at + ?) / 86400) d, COUNT(*) n FROM events WHERE type='ad_impression' AND at>=? AND at<?"
        args = [TZ, frm, to]
        if devices_f:
            sql += f" AND device_code IN ({','.join('?' * len(devices_f))})"
            args += devices_f
        by_day, by_dev, by_ad, rows = {}, {}, {}, []
        for r in q(sql + " GROUP BY data, device_code, d", tuple(args)):
            try:
                aid = int(json.loads(r["data"] or "{}").get("ad"))
            except Exception:
                continue
            if ad_ids and aid not in ad_ids:
                continue
            k = time.strftime("%Y-%m-%d", time.gmtime(int(r["d"]) * DAY))
            n = int(r["n"])
            by_day[k] = by_day.get(k, 0) + n
            by_dev[r["device_code"] or "web"] = by_dev.get(r["device_code"] or "web", 0) + n
            by_ad[aid] = by_ad.get(aid, 0) + n
            rows.append((k, r["device_code"] or "web", aid, n))
        titles = {r["id"]: r["title"] for r in q("SELECT id, title FROM ads")}
        devn = {r["code"]: r["name"] for r in q("SELECT code, name FROM devices")}
        if request.args.get("format") == "csv":
            buf = io.StringIO()
            buf.write("﻿")
            w = csv.writer(buf)
            w.writerow(["Ngày", "Mã màn hình", "Tên màn hình", "Mã quảng cáo", "Quảng cáo", "Lượt hiển thị"])
            for k, dv, aid, n in sorted(rows):
                w.writerow([k, dv, devn.get(dv, ""), aid, titles.get(aid, ""), n])
            fn = f"xanh24-bao-cao-quang-cao-{time.strftime('%Y%m%d', time.gmtime(t + TZ))}.csv"
            return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{fn}"'})
        days = []
        d = day_start(frm)
        while d < to and len(days) < 400:
            k = day_key(d)
            days.append({"day": k, "n": by_day.get(k, 0)})
            d += DAY
        return jsonify(title=title, total=sum(by_day.values()), days=days,
                       devices=sorted(({"code": k, "name": devn.get(k, ""), "n": v} for k, v in by_dev.items()), key=lambda x: -x["n"]),
                       ads=sorted(({"id": k, "title": titles.get(k, f"#{k}"), "n": v} for k, v in by_ad.items()), key=lambda x: -x["n"]),
                       rows=len(rows))
