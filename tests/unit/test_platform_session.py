"""U5.2: cerrar sesión y mantener despierto con systemd-inhibit como último recurso."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.session import (INHIBIT_METHODS, LOGOUT_METHODS, Session,  # noqa: E402
                                             inhibit_argv, logout_call)

GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})
KDE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"})
X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "LXDE"})


def tools(cmds=(), names=()):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names)


class FakeBus:
    def __init__(self, cookie=42):
        self.cookie, self.calls = cookie, []

    def call_sync(self, *args):
        self.calls.append(args)
        if args[3] == "Inhibit":
            class R:
                def unpack(inner):
                    return (self.cookie,)
            return R()
        return None

    def call(self, *args):
        self.calls.append(args)


class SessionTest(unittest.TestCase):
    def test_logout_chain(self):
        self.assertEqual(pick(LOGOUT_METHODS, tools(names={"org.gnome.SessionManager"}), GNOME).name,
                         "GNOME SessionManager")
        self.assertEqual(pick(LOGOUT_METHODS, tools(names={"org.kde.ksmserver"}), KDE).name, "KDE ksmserver")
        self.assertEqual(pick(LOGOUT_METHODS, tools(), X11).name, "loginctl")

    def test_logout_call(self):
        m = pick(LOGOUT_METHODS, tools(), X11)
        self.assertEqual(logout_call(m), ["loginctl", "terminate-session"])
        gnome = pick(LOGOUT_METHODS, tools(names={"org.gnome.SessionManager"}), GNOME)
        self.assertEqual(logout_call(gnome)[0], "org.gnome.SessionManager")
        self.assertEqual(logout_call(gnome)[3], "Logout")

    def test_inhibit_chain_and_argv(self):
        self.assertEqual(pick(INHIBIT_METHODS, tools(names={"org.gnome.SessionManager"}), GNOME).name,
                         "GNOME SessionManager")
        self.assertEqual(pick(INHIBIT_METHODS, tools(cmds={"systemd-inhibit"}), X11).name, "systemd-inhibit")
        self.assertEqual(inhibit_argv(pick(INHIBIT_METHODS, tools(cmds={"systemd-inhibit"}), X11)),
                         ["systemd-inhibit", "--what=idle", "--why=Isla dinámica", "sleep", "infinity"])

    def test_session_uses_bus_then_falls_back(self):
        bus, spawned, changes = FakeBus(), [], []
        s = Session(bus, lambda: changes.append(1),
                    tools=tools(cmds={"systemd-inhibit"}, names={"org.gnome.SessionManager"}), desktop=X11,
                    spawn=lambda argv: spawned.append(argv) or object())
        self.assertTrue(s.set_awake(True))
        self.assertTrue(s.awake)
        self.assertEqual(bus.calls[-1][3], "Inhibit")
        s.set_awake(False)
        self.assertFalse(s.awake)
        self.assertEqual(bus.calls[-1][3], "Uninhibit")

        bus2 = FakeBus()
        bus2.call_sync = lambda *a: (_ for _ in ()).throw(RuntimeError("sin sesión"))
        s2 = Session(bus2, lambda: None,
                     tools=tools(cmds={"systemd-inhibit"}, names={"org.gnome.SessionManager"}), desktop=X11,
                     spawn=lambda argv: spawned.append(argv) or object())
        self.assertTrue(s2.set_awake(True))
        self.assertEqual(spawned[-1][0], "systemd-inhibit")
        self.assertTrue(s2.awake)
        s2.set_awake(False)
        self.assertFalse(s2.awake)


if __name__ == "__main__":
    unittest.main()
