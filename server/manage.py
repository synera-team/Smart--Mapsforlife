"""Công cụ quản trị dòng lệnh.

  python server/manage.py init                      # tạo CSDL + dữ liệu nền (chạy 1 lần trước gunicorn)
  python server/manage.py create-user <user> <S0|S1|CW> <mật khẩu> ["Họ tên"]
  python server/manage.py reset-password <user> <mật khẩu mới>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import ex, init_db, now, q  # noqa: E402


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return 0
    cmd = argv[0]
    init_db()
    if cmd == "init":
        from seed import seed_all
        seed_all()
        print("OK — CSDL sẵn sàng")
    elif cmd == "create-user":
        from auth import hash_password, password_problem
        user, role, pw = argv[1], argv[2], argv[3]
        name = argv[4] if len(argv) > 4 else user
        if role not in ("S0", "S1", "CW"):
            print("Vai trò phải là S0, S1 hoặc CW"); return 1
        p = password_problem(pw)
        if p:
            print(p); return 1
        ex("INSERT INTO users(username,password_hash,full_name,role,created_at) VALUES(?,?,?,?,?)", (user.lower(), hash_password(pw), name, role, now()))
        print("Đã tạo", user, role)
    elif cmd == "reset-password":
        from auth import hash_password
        if not q("SELECT 1 FROM users WHERE lower(username)=?", (argv[1].lower(),), one=True):
            print("Không có người dùng"); return 1
        ex("UPDATE users SET password_hash=?, must_change_password=1, active=1 WHERE lower(username)=?", (hash_password(argv[2]), argv[1].lower()))
        print("Đã đặt lại mật khẩu cho", argv[1])
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
