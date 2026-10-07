"""Module mẫu phía máy chủ: tiếp nhận góp ý/phản ánh từ màn hình kiosk.

Minh hoạ cách một module mới gắn thêm bảng dữ liệu + API mà không sửa mã lõi.
Giao diện tương ứng: web/modules/sample/feedback.html (được nạp dạng iframe trên kiosk).
"""
import json
import time

from flask import jsonify, request

KEY = "feedback"


def register(app, ctx):
    ctx.ex("""CREATE TABLE IF NOT EXISTS mod_feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT, device TEXT, ward TEXT, topic TEXT, content TEXT,
        contact TEXT, status TEXT DEFAULT 'new', at INTEGER)""")

    @app.route(f"/api/modules/{KEY}/submit", methods=["POST"], endpoint=f"mod_{KEY}_submit")
    def submit():
        d = request.get_json(silent=True) or {}
        content = str(d.get("content") or "").strip()
        if len(content) < 5:
            return jsonify(error="Nội dung quá ngắn"), 400
        fid = ctx.ex("INSERT INTO mod_feedback(device,ward,topic,content,contact,at) VALUES(?,?,?,?,?,?)",
                     (str(d.get("device") or "")[:40], str(d.get("ward") or "")[:60], str(d.get("topic") or "")[:80],
                      content[:3000], str(d.get("contact") or "")[:120], int(time.time())))
        ctx.fire_webhook("module.feedback.new", {"id": fid})
        return jsonify(ok=True, id=fid)

    @app.route(f"/api/modules/{KEY}/list", endpoint=f"mod_{KEY}_list")
    @ctx.require("poi.read")
    def list_():
        rows = ctx.q("SELECT * FROM mod_feedback ORDER BY id DESC LIMIT 200")
        return jsonify(items=[dict(r) for r in rows])
