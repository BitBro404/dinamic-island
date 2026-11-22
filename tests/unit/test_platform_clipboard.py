"""U4.1: vigilar y copiar el portapapeles con wl-clipboard o Gtk.Clipboard (X11/XWayland)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.clipboard import METHODS, FEATURE, GtkSource, copy_text  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

WLR = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"})
X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})


def tools(cmds=()):
    return Tools(which=lambda c: c if c in cmds else None)


class FakeClipboard:
    def __init__(self, text=""):
        self.text, self.cb = text, None
        self.written = None
        self.stored = False

    def connect(self, sig, cb):
        self.cb = cb

    def wait_for_text(self):
        return self.text

    def set_text(self, text, n):
        self.written = text

    def store(self):
        self.stored = True


class ClipboardTest(unittest.TestCase):
    def test_wl_paste_first_on_wlroots(self):
        m = pick(METHODS, tools(cmds={"wl-paste", "wl-copy"}), WLR)
        self.assertEqual(m.name, "wl-paste --watch")
        self.assertEqual(m.act[0], "process")
        self.assertIn("wl-paste", m.act[1][0])

    def test_gtk_fallback_on_x11(self):
        m = pick(METHODS, tools(), X11)
        self.assertEqual(m.name, "Gtk.Clipboard")
        self.assertEqual(m.act[0], "gtk")
        self.assertEqual(FEATURE[0], "Portapapeles")

    def test_gtk_source_forwards_changes(self):
        got, fake = [], FakeClipboard("hola")
        GtkSource(got.append, clipboard=fake)
        fake.cb()
        self.assertEqual(got, ["hola"])
        fake.text = "   "                # vacío: no se guarda
        fake.cb()
        self.assertEqual(got, ["hola"])

    def test_copy_uses_wl_copy_when_available(self):
        calls = []
        copy_text("hola", tools(cmds={"wl-copy"}), WLR,
                  run=lambda argv, stdin=None: calls.append((argv, stdin)))
        self.assertEqual(calls, [(["wl-copy"], "hola")])

    def test_copy_falls_back_to_gtk(self):
        fake = FakeClipboard()
        copy_text("hola", tools(), X11, clipboard=fake)
        self.assertEqual(fake.written, "hola")
        self.assertTrue(fake.stored)


if __name__ == "__main__":
    unittest.main()
