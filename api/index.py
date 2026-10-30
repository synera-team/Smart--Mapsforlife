"""Điểm vào Vercel: chỉ xử lý /api/* và /uploads/*.
Giao diện (web/) do Vercel phục vụ trực tiếp như tệp tĩnh (outputDirectory = web).
Đường dẫn gốc được truyền qua tham số ?__p=… trong vercel.json để Flask định tuyến đúng.
"""
import os
import sys
from urllib.parse import parse_qsl, urlencode
from flask_cors import CORS
SERVER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server"))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from app import create_app  # noqa: E402

app = create_app()
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

class OriginalPathMiddleware:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        qs = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        orig = [v for k, v in qs if k == "__p"]
        if orig:
            environ["PATH_INFO"] = orig[0]
            environ["QUERY_STRING"] = urlencode([(k, v) for k, v in qs if k != "__p"])
        else:
            path = environ.get("PATH_INFO", "")
            for prefix in ("/api/index.py", "/api/index"):
                if path == prefix or path.startswith(prefix + "/"):
                    environ["PATH_INFO"] = path[len(prefix):] or "/"
                    break
        return self.application(environ, start_response)


app.wsgi_app = OriginalPathMiddleware(app.wsgi_app)
