"""S3: solo se abren en el navegador URLs web seguras (las de despliegues y PR vienen de terceros)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.util import safety  # noqa: E402


class SafeUrlTest(unittest.TestCase):
    def test_accepts_https(self):
        for u in ("https://github.com/o/r/pull/1", "https://railway.app/project/x?env=1"):
            self.assertTrue(safety.is_safe_web_url(u), u)

    def test_accepts_plain_http_only_for_this_machine(self):
        self.assertTrue(safety.is_safe_web_url("http://localhost:5173/"))
        self.assertTrue(safety.is_safe_web_url("http://127.0.0.1:8000"))
        self.assertFalse(safety.is_safe_web_url("http://example.com/"))

    def test_rejects_other_schemes_and_junk(self):
        for u in ("file:///etc/passwd", "javascript:alert(1)", "ssh://host", "x-scheme-handler://a",
                  "https://", "", None, "  https://github.com", "https://user:pw@evil.com/"):
            self.assertFalse(safety.is_safe_web_url(u), repr(u))

    def test_open_web_ignores_unsafe(self):
        opened = []
        old = safety.open_uri
        safety.open_uri = opened.append
        try:
            self.assertFalse(safety.open_web("file:///etc/passwd"))
            self.assertTrue(safety.open_web("https://github.com/"))
        finally:
            safety.open_uri = old
        self.assertEqual(opened, ["https://github.com/"])


class DeployUrlTest(unittest.TestCase):
    def test_unsafe_deploy_url_falls_back_to_github(self):
        from isla_dinamica.services.deploys import deploy_url
        self.assertEqual(deploy_url({"logUrl": "file:///etc/passwd"}, "o/r"), "https://github.com/o/r/deployments")
        self.assertEqual(deploy_url({"logUrl": "https://railway.app/x"}, "o/r"), "https://railway.app/x")
        self.assertEqual(deploy_url({"environmentUrl": "https://app.x.com"}, "o/r"), "https://app.x.com")
        self.assertEqual(deploy_url(None, "o/r"), "https://github.com/o/r/deployments")


if __name__ == "__main__":
    unittest.main()
