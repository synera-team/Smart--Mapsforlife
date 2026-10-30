#!/usr/bin/env sh
# Chạy thử nhanh trên máy cá nhân: ./run.sh  → http://localhost:8024  (quản trị: /admin)
set -e
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
python3 server/manage.py init
exec python3 server/app.py
