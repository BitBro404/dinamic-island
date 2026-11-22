"""U3.2: apagar y encender la pantalla con el mejor método disponible (argv por método)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.screen import METHODS, Screen  # noqa: E402

X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
WLR = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"})
GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})


def tools(cmds=(), names=()):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names)


class FakeBus:
    def __init__(self):
        self.calls = []

    def call(self, *args):
        self.calls.append(args)


class ScreenTest(unittest.TestCase):
    def test_wlopm_is_first_on_wlroots(self):
        m = pick(METHODS, tools(cmds={"wlopm"}), WLR)
        self.assertEqual(m.name, "wlopm")
        self.assertEqual(m.act[0], ("cmd", ["wlopm", "--off", "*"]))
        self.assertEqual(m.act[1], ("cmd", ["wlopm", "--on", "*"]))

    def test_xset_is_last_resort_on_x11(self):
        m = pick(METHODS, tools(cmds={"xset"}), X11)
        self.assertEqual(m.name, "xset")
        self.assertEqual(m.act[0], ("cmd", ["xset", "dpms", "force", "off"]))
        self.assertEqual(m.act[1], ("cmd", ["xset", "dpms", "force", "on"]))

    def test_off_and_on_use_the_same_method(self):
        calls = []
        s = Screen(FakeBus(), tools=tools(cmds={"xset"}), desktop=X11, run=lambda argv: calls.append(argv) or 1)
        self.assertTrue(s.off())
        self.assertTrue(s.on())
        self.assertEqual(calls, [["xset", "dpms", "force", "off"], ["xset", "dpms", "force", "on"]])

    def test_gnome_extension_uses_dbus(self):
        bus = FakeBus()
        s = Screen(bus, tools=tools(names={"io.github.bitbro404.IslaDinamica.Shell"}), desktop=GNOME)
        self.assertTrue(s.off())
        self.assertIn("SetPowerSave", bus.calls[-1])
        self.assertFalse(bus.calls[-1][4].unpack()[0])

    def test_without_method_nothing_happens(self):
        calls = []
        s = Screen(FakeBus(), tools=tools(), desktop=X11, methods=[], run=lambda argv: calls.append(argv))
        self.assertFalse(s.supported)
        self.assertFalse(s.off())
        self.assertFalse(s.on())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
