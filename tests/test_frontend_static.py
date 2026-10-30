"""Smoke test the built React pages through the production Flask static routes."""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
from app import app  # noqa: E402


@unittest.skipUnless(os.path.isfile(os.path.join(ROOT, "frontend", "dist", "index.html")), "build frontend first")
class FrontendStaticTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_pages_and_bundles(self):
        page_html = []
        for path in ("/", "/admin", "/download", "/go/grab"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                if path == "/admin":
                    self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex")
                elif path == "/download":
                    self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")
                html = response.get_data(as_text=True)
                response.close()
                self.assertIn('id="react-root"', html)
                page_html.append(html)
                for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html):
                    file_response = self.client.get(asset)
                    self.assertEqual(file_response.status_code, 200, asset)
                    file_response.close()
        self.assertTrue(all(html == page_html[0] for html in page_html[1:]))

    def test_legacy_static_assets_and_private_apks(self):
        for path in ("/vendor/maplibre-gl.js", "/assets/logo.png", "/sw.js"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        response = self.client.get("/downloads/Xanh24-Kiosk.apk")
        self.assertEqual(response.status_code, 404)
        response.close()


if __name__ == "__main__":
    unittest.main()
