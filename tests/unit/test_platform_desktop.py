"""U0.1: detectar el escritorio y la sesión a partir de las variables de entorno (sin escritorio real)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.desktop import detect  # noqa: E402

W = {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}
X = {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}

CASES = [
    # (entorno, familia, sesión, wlr)
    (dict(W, XDG_CURRENT_DESKTOP="Budgie", LABWC_PID="3537"), "budgie", "wayland", True),
    (dict(X, XDG_CURRENT_DESKTOP="Budgie:GNOME"), "budgie", "x11", False),
    (dict(W, XDG_CURRENT_DESKTOP="ubuntu:GNOME"), "gnome", "wayland", False),
    (dict(W, XDG_CURRENT_DESKTOP="GNOME"), "gnome", "wayland", False),
    (dict(W, XDG_CURRENT_DESKTOP="pop:GNOME"), "gnome", "wayland", False),
    (dict(W, XDG_CURRENT_DESKTOP="KDE"), "kde", "wayland", False),
    (dict(X, XDG_CURRENT_DESKTOP="KDE"), "kde", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="X-Cinnamon"), "cinnamon", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="MATE"), "mate", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="XFCE"), "xfce", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="LXDE"), "lxde", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="LXQt"), "lxqt", "x11", False),
    (dict(W, XDG_CURRENT_DESKTOP="LXQt", LABWC_PID="1"), "lxqt", "wayland", True),
    (dict(X, XDG_CURRENT_DESKTOP="Pantheon"), "pantheon", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="Deepin"), "deepin", "x11", False),
    (dict(X, XDG_CURRENT_DESKTOP="Unity"), "unity", "x11", False),
    (dict(W, XDG_CURRENT_DESKTOP="sway"), "sway", "wayland", True),
    (dict(W, XDG_CURRENT_DESKTOP="Hyprland"), "hyprland", "wayland", True),
    (dict(W, XDG_CURRENT_DESKTOP="wayfire"), "wayfire", "wayland", True),
    (dict(W, XDG_CURRENT_DESKTOP="river"), "river", "wayland", True),
    (dict(W, XDG_CURRENT_DESKTOP="labwc:wlroots"), "labwc", "wayland", True),
    (dict(W, XDG_CURRENT_DESKTOP="niri"), "niri", "wayland", False),
    (dict(W, XDG_CURRENT_DESKTOP="COSMIC"), "cosmic", "wayland", False),
    # sin XDG_CURRENT_DESKTOP: otras pistas
    (dict(X, DESKTOP_SESSION="LXDE"), "lxde", "x11", False),
    (dict(X, DESKTOP_SESSION="/usr/share/xsessions/plasma"), "kde", "x11", False),
    (dict(W, SWAYSOCK="/run/user/1000/sway.sock"), "sway", "wayland", True),
    (dict(W, HYPRLAND_INSTANCE_SIGNATURE="abc"), "hyprland", "wayland", True),
    ({"DISPLAY": ":0"}, "other", "x11", False),
    ({"WAYLAND_DISPLAY": "wayland-1"}, "other", "wayland", False),
    ({}, "other", "unknown", False),
]


class DetectTest(unittest.TestCase):
    def test_table(self):
        for env, family, session, wlr in CASES:
            with self.subTest(env=env):
                d = detect(env)
                self.assertEqual((d.family, d.session, d.wlr), (family, session, wlr))

    def test_this_machine_style_budgie_is_wayland_wlr(self):
        d = detect({"XDG_CURRENT_DESKTOP": "Budgie", "XDG_SESSION_TYPE": "wayland", "LABWC_PID": "1",
                    "WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":1"})
        self.assertTrue(d.wayland)
        self.assertTrue(d.xwayland)

    def test_session_type_tty_with_display_is_x11(self):
        self.assertEqual(detect({"XDG_SESSION_TYPE": "tty", "DISPLAY": ":0"}).session, "x11")

    def test_label_is_human(self):
        self.assertEqual(detect(dict(W, XDG_CURRENT_DESKTOP="KDE")).label, "KDE Plasma · Wayland")


if __name__ == "__main__":
    unittest.main()
