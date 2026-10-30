import os
import sys
import tempfile
import unittest
from unittest.mock import patch


class DownloadPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["XANH24_DATA_DIR"] = cls.temp_dir.name
        os.environ["XANH24_DB"] = os.path.join(cls.temp_dir.name, "test.db")
        os.environ["XANH24_ADMIN_PASSWORD"] = "Admin@2026x"
        os.environ["XANH24_DOWNLOAD_PIN"] = "123456"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(root, "server"))
        import db
        import media
        from app import create_app

        db.UPLOAD_DIR = os.path.join(cls.temp_dir.name, "uploads")
        media.UPLOAD_DIR = db.UPLOAD_DIR
        cls.client = create_app().test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()
        for name in ("XANH24_DATA_DIR", "XANH24_DB", "XANH24_ADMIN_PASSWORD", "XANH24_DOWNLOAD_PIN"):
            os.environ.pop(name, None)

    def test_downloads_require_pin_and_are_served_via_backend(self):
        page = self.client.get("/download")
        self.assertEqual(page.status_code, 200)
        page.close()
        self.assertEqual(self.client.get("/api/download/files").status_code, 401)
        self.assertEqual(self.client.get("/api/download/file/Xanh24-Kiosk.apk").status_code, 401)
        public_file = self.client.get("/downloads/Xanh24-Kiosk.apk")
        self.assertEqual(public_file.status_code, 404)
        public_file.close()

        wrong_pin = self.client.post("/api/download/login", json={"pin": "wrong"})
        self.assertEqual(wrong_pin.status_code, 401)
        unlocked = self.client.post("/api/download/login", json={"pin": "123456"})
        self.assertEqual(unlocked.status_code, 200)

        result = self.client.get("/api/download/files")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json["files"]), 1)
        item = result.json["files"][0]
        self.assertEqual(item["name"], "LCD_kiosk_Dong_Do_ver 1.0.0.apk")
        self.assertEqual(item["title"], "LCD Kiosk · Đại học Đông Đô")
        self.assertEqual(item["version"], "1.0.0")
        self.assertEqual(item["size"], 4353971)
        self.assertTrue(all("drive.google.com" not in item["url"] for item in result.json["files"]))
        self.assertNotIn("drive_id", item)
        self.assertEqual(self.client.get("/api/download/file/Xanh24-Kiosk.apk").status_code, 404)

        confirmation_html = (
            b'<p>Google Drive can\'t scan this file for viruses.</p>'
            b'<form><input type="hidden" name="uuid" value="a12db165-4f13-4ca8-bb33-620ba5643d7b"></form>'
        )
        apk_contents = b"PK\x03\x04sample-test-apk"

        class Upstream:
            def __init__(self, content, content_type):
                self.content = content
                self.headers = {"Content-Type": content_type, "Content-Length": str(len(content))}

            def read(self, size=-1):
                if not self.content:
                    return b""
                chunk, self.content = self.content[:size], self.content[size:]
                return chunk

            def close(self):
                pass

        with patch(
            "urllib.request.urlopen",
            side_effect=[
                Upstream(confirmation_html, "text/html"),
                Upstream(apk_contents, "application/octet-stream"),
            ],
        ) as open_url:
            apk = self.client.get(item["url"])
        self.assertEqual(apk.status_code, 200)
        self.assertIn("attachment", apk.headers["Content-Disposition"])
        self.assertEqual(apk.mimetype, "application/vnd.android.package-archive")
        self.assertEqual(apk.data, apk_contents)
        confirmed_url = open_url.call_args_list[1].args[0]
        self.assertIn("drive.usercontent.google.com", confirmed_url)
        self.assertIn("confirm=t", confirmed_url)
        self.assertIn("uuid=a12db165-4f13-4ca8-bb33-620ba5643d7b", confirmed_url)
        self.assertNotIn("drive.google.com", apk.headers["Content-Disposition"])
        apk.close()

        self.client.post("/api/download/logout")
        self.assertEqual(self.client.get("/api/download/files").status_code, 401)


if __name__ == "__main__":
    unittest.main()
