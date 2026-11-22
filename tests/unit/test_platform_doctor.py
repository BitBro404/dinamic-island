"""U0.3: --doctor dice qué método usa cada función y qué instalar cuando falta."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Method, Tools  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.doctor import all_features, report  # noqa: E402

D = detect({"XDG_CURRENT_DESKTOP": "XFCE", "XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"})
TOOLS = Tools(which=lambda c: c if c in {"maim"} else None, has_name=lambda n: False, has_schema=lambda s: False)
FEATURES = [
    ("Captura", [Method("grim + slurp", lambda t, d: t.has("grim", "slurp"), hint="grim slurp"),
                 Method("maim", lambda t, d: t.has("maim"), hint="maim")]),
    ("Grabación", [Method("wf-recorder", lambda t, d: t.has("wf-recorder"), hint="wf-recorder"),
                   Method("ffmpeg", lambda t, d: t.has("ffmpeg"), hint="ffmpeg")]),
]


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.text = report(D, TOOLS, FEATURES, window="X11")

    def test_header(self):
        self.assertIn("XFCE · X11", self.text)
        self.assertIn("Ventana: X11", self.text)

    def test_available_method(self):
        line = next(ln for ln in self.text.splitlines() if "Captura" in ln)
        self.assertIn("maim", line)

    def test_missing_shows_what_to_install(self):
        line = next(ln for ln in self.text.splitlines() if "Grabación" in ln)
        self.assertIn("no disponible", line)
        self.assertIn("wf-recorder", line)
        self.assertIn("ffmpeg", line)

    def test_real_features_are_registered(self):
        titles = {title for title, _methods in all_features()}
        self.assertTrue({"Avisos", "No molestar", "Centro de avisos", "Bloqueo", "Apagar pantalla",
                         "Inactividad", "Portapapeles", "Captura de pantalla", "Grabación", "Modo oscuro",
                         "Luz nocturna", "Cerrar sesión", "Mantener despierto", "Volumen", "Sonidos"} <= titles)


if __name__ == "__main__":
    unittest.main()
