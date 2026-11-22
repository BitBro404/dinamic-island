"""U1: cómo se coloca la ventana según el escritorio (layer-shell, X11 o relanzar en XWayland)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.ui.placement import choose_backend, x11_origin  # noqa: E402


def d(cur, session, **extra):
    env = {"XDG_CURRENT_DESKTOP": cur, "XDG_SESSION_TYPE": session}
    env.update({"WAYLAND_DISPLAY": "wayland-0"} if session == "wayland" else {"DISPLAY": ":0"})
    env.update(extra)
    return env


class ChooseBackendTest(unittest.TestCase):
    def choose(self, env, layer_shell, gnome_ext=False):
        return choose_backend(detect(env), env, layer_shell, gnome_ext)

    def test_wayland_with_layer_shell(self):
        for cur in ("Budgie", "KDE", "sway", "Hyprland", "LXQt"):
            self.assertEqual(self.choose(d(cur, "wayland"), True), "layer-shell", cur)

    def test_any_x11_session(self):
        for cur in ("X-Cinnamon", "LXDE", "XFCE", "MATE", "KDE", "GNOME"):
            self.assertEqual(self.choose(d(cur, "x11"), False), "x11", cur)

    def test_gnome_wayland_relaunches_in_xwayland(self):
        self.assertEqual(self.choose(d("GNOME", "wayland", DISPLAY=":0"), False), "relaunch-x11")

    def test_gnome_wayland_with_extension_stays_native(self):
        self.assertEqual(self.choose(d("GNOME", "wayland", DISPLAY=":0"), False, gnome_ext=True), "gnome-shell")

    def test_relaunch_only_once(self):
        env = d("GNOME", "wayland", DISPLAY=":0", ISLA_RELAUNCHED="1")
        self.assertEqual(self.choose(env, False), "toplevel")

    def test_wayland_without_xwayland_is_plain_toplevel(self):
        self.assertEqual(self.choose(d("Weston", "wayland"), False), "toplevel")

    def test_after_relaunch_gdk_backend_x11_means_x11(self):
        env = d("GNOME", "wayland", DISPLAY=":0", GDK_BACKEND="x11", ISLA_RELAUNCHED="1")
        self.assertEqual(self.choose(env, False), "x11")


class X11OriginTest(unittest.TestCase):
    def test_adds_monitor_origin(self):
        self.assertEqual(x11_origin(100, 6, (1920, 0)), (2020, 6))
        self.assertEqual(x11_origin(0, 0, (0, 1080)), (0, 1080))


if __name__ == "__main__":
    unittest.main()
