"""S6–S9: riesgos bajos (abrir descargas, avisos que lanzan apps, registro de depuración, permisos)."""
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import config  # noqa: E402
from isla_dinamica.util import safety  # noqa: E402


class DownloadOpenTest(unittest.TestCase):
    """S6: lo ejecutable o desconocido se muestra en la carpeta, no se abre con un clic."""

    def test_documents_and_media_open_directly(self):
        for name in ("foto.png", "informe.pdf", "video.mp4", "notas.txt", "datos.csv", "musica.mp3"):
            self.assertTrue(safety.safe_to_open(name), name)

    def test_executables_and_unknown_do_not(self):
        for name in ("instalar.sh", "app.desktop", "setup.exe", "x.AppImage", "paquete.deb", "script.py",
                     "macro.docm", "algo.jar", "sin_extension", "web.html", "atajo.lnk", "x.run"):
            self.assertFalse(safety.safe_to_open(name), name)


class NotifLaunchTest(unittest.TestCase):
    """S7: un aviso solo puede abrir la app que lo envió, no cualquier app instalada."""

    def test_desktop_entry_must_match_app(self):
        self.assertTrue(safety.desktop_matches_app("org.gnome.Nautilus", "Nautilus"))
        self.assertTrue(safety.desktop_matches_app("firefox", "Firefox"))
        self.assertTrue(safety.desktop_matches_app("google-chrome", "Google Chrome"))
        self.assertFalse(safety.desktop_matches_app("org.gnome.Terminal", "Spotify"))
        self.assertFalse(safety.desktop_matches_app("", "Spotify"))


class DebugLogTest(unittest.TestCase):
    """S8: con ISLA_DEBUG no se imprime el contenido de los avisos."""

    def test_notif_debug_line_has_no_content(self):
        line = safety.notif_debug_line({"app": "Microsoft Teams", "desktop": "chrome-x", "summary": "Ana",
                                        "body": "clave del banco: 1234"}, "teams")
        self.assertIn("Microsoft Teams", line)
        self.assertNotIn("Ana", line)
        self.assertNotIn("1234", line)


class ConfigPermsTest(unittest.TestCase):
    """S9: config.json solo lo puede leer su dueño."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = config.CONFIG_PATH
        config.CONFIG_PATH = os.path.join(self.dir.name, "sub", "config.json")

    def tearDown(self):
        config.CONFIG_PATH = self.old
        self.dir.cleanup()

    def test_saved_with_0600(self):
        old_umask = os.umask(0o022)
        try:
            config.Config().save()
        finally:
            os.umask(old_umask)
        mode = stat.S_IMODE(os.stat(config.CONFIG_PATH).st_mode)
        self.assertEqual(mode, 0o600)
        with open(config.CONFIG_PATH) as f:
            self.assertIn("presence", json.load(f))


if __name__ == "__main__":
    unittest.main()
