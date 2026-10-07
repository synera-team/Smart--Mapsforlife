"""Điểm vào WSGI cho gunicorn:  gunicorn -w 4 -b 0.0.0.0:8024 wsgi:app  (chạy trong thư mục server/)"""
from app import create_app

app = create_app()
