"""U3.1: bloquear por el mejor método disponible, con verificación (S2: sin éxito no se apaga la pantalla)."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gi.repository import GLib  # noqa: E402

from isla_dinamica.platform.chain import Method, Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.lock import Locker, METHODS  # noqa: E402

X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
BUDGIE = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "Budgie"})


def tools(cmds=(), names=()):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names)


class FakeBus:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def call_sync(self, dest, path, iface, method, params, reply_type, *_args):
        self.calls.append((dest, path, iface, method))
        if not self.ok:
            raise GLib.Error("rechazado")
        return None


class LockTest(unittest.TestCase):
    def test_budgie_stays_first(self):
        m = pick(METHODS, tools(names={"org.buddiesofbudgie.BudgieScreenlock"}), BUDGIE)
        self.assertEqual(m.name, "Budgie Screenlock")

    def test_loginctl_when_no_desktop_method(self):
        m = pick(METHODS, tools(cmds={"loginctl"}), X11)
        self.assertEqual(m.name, "loginctl")

    def test_swaylock_on_wlroots(self):
        m = pick(METHODS, tools(cmds={"swaylock"}), detect(
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"}))
        self.assertEqual(m.name, "swaylock")

    def test_dbus_success_is_verified(self):
        bus = FakeBus()
        locker = Locker(bus, tools=tools(names={"org.freedesktop.ScreenSaver"}), desktop=X11)
        self.assertTrue(locker.lock())
        self.assertEqual(bus.calls[-1][0], "org.freedesktop.ScreenSaver")

    def test_dbus_failure_returns_false(self):
        locker = Locker(FakeBus(ok=False), tools=tools(names={"org.freedesktop.ScreenSaver"}), desktop=X11)
        self.assertFalse(locker.lock())

    def test_command_failure_returns_false(self):
        with patch("isla_dinamica.platform.lock._command_ok", return_value=False):
            locker = Locker(FakeBus(), tools=tools(cmds={"loginctl"}), desktop=X11)
            self.assertFalse(locker.lock())

    def test_no_method_returns_false(self):
        locker = Locker(FakeBus(), tools=tools(), desktop=X11, methods=[])
        self.assertFalse(locker.supported)
        self.assertFalse(locker.lock())

    def test_broken_method_returns_false(self):
        broken = [Method("roto", lambda t, d: True, lambda bus: lambda: (_ for _ in ()).throw(RuntimeError()))]
        self.assertFalse(Locker(FakeBus(), tools=tools(), desktop=X11, methods=broken).lock())


if __name__ == "__main__":
    unittest.main()
