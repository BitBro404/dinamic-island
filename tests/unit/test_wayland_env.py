"""Si la isla hereda un entorno X11 (p. ej. lanzada desde Plank, que corre en XWayland) pero hay una sesión
Wayland viva, vuelve a Wayland: así usa la capa overlay y ninguna ventana maximizada la tapa."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.session_env import wayland_env  # noqa: E402

PLANK = {"GDK_BACKEND": "x11", "XDG_SESSION_TYPE": "x11", "DISPLAY": ":1", "XDG_RUNTIME_DIR": "/run/user/1000"}


class WaylandEnvTest(unittest.TestCase):
    def test_inherited_x11_with_live_wayland_socket_goes_back_to_wayland(self):
        env = wayland_env(PLANK, ["wayland-0", "wayland-0.lock", "bus"])
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-0")
        self.assertEqual(env["XDG_SESSION_TYPE"], "wayland")
        self.assertNotIn("GDK_BACKEND", env)
        self.assertEqual(env["DISPLAY"], ":1")          # XWayland sigue disponible para lo que lo necesite

    def test_real_x11_session_is_left_alone(self):
        self.assertIsNone(wayland_env(PLANK, ["bus", "pulse"]))

    def test_deliberate_xwayland_relaunch_is_respected(self):
        self.assertIsNone(wayland_env(dict(PLANK, ISLA_RELAUNCHED="1"), ["wayland-0"]))

    def test_user_can_force_x11(self):
        self.assertIsNone(wayland_env(dict(PLANK, ISLA_FORCE_X11="1"), ["wayland-0"]))

    def test_already_wayland_needs_nothing(self):
        self.assertIsNone(wayland_env({"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"},
                                      ["wayland-0"]))

    def test_lowest_numbered_socket_wins(self):
        self.assertEqual(wayland_env(PLANK, ["wayland-1", "wayland-0"])["WAYLAND_DISPLAY"], "wayland-0")


if __name__ == "__main__":
    unittest.main()
