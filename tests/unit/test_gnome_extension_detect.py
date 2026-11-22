"""U7.3: la isla elige la extensión de GNOME cuando el nombre está en el bus (lado Python)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.capture import METHODS as CAPTURE  # noqa: E402
from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.dnd import CENTER  # noqa: E402
from isla_dinamica.platform.idle import METHODS as IDLE  # noqa: E402
from isla_dinamica.platform.record import METHODS as RECORD  # noqa: E402
from isla_dinamica.platform.screen import METHODS as SCREEN, SHELL_BUS  # noqa: E402

GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})
TOOLS = Tools(which=lambda c: None, has_name=lambda n: n == SHELL_BUS,
              has_schema=lambda s: False, notif_server=lambda: "gnome-shell")


class ExtensionDetectTest(unittest.TestCase):
    def test_screen_capture_record_and_center_use_the_extension(self):
        for methods in (SCREEN, CAPTURE, RECORD):
            self.assertEqual(pick(methods, TOOLS, GNOME).name, "GNOME Shell (extensión)")
        self.assertEqual(pick(CENTER, TOOLS, GNOME).name, "GNOME (extensión de la isla)")

    def test_idle_also_uses_the_shell_bus(self):
        self.assertEqual(pick(IDLE, TOOLS, GNOME).name, "GNOME IdleMonitor")

    def test_without_extension_other_methods_are_used(self):
        tools = Tools(which=lambda c: c if c in {"xset", "maim", "ffmpeg"} else None,
                      has_name=lambda n: False, has_schema=lambda s: False, notif_server=lambda: "gnome-shell")
        self.assertEqual(pick(SCREEN, tools, GNOME).name, "xset")
        self.assertEqual(pick(CAPTURE, tools, GNOME).name, "maim")


if __name__ == "__main__":
    unittest.main()
