"""U5.3: abrir ajustes y el monitor del sistema con la app de cada escritorio."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.apps import monitor_command, settings_command  # noqa: E402
from isla_dinamica.platform.chain import Tools  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

BUDGIE = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "Budgie"})
GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})
KDE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"})
XFCE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
LXDE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "LXDE"})


def tools(*cmds):
    return Tools(which=lambda c: c if c in cmds else None)


class AppsTest(unittest.TestCase):
    def test_settings_by_panel_and_desktop(self):
        self.assertEqual(settings_command("wifi", tools("budgie-control-center"), BUDGIE),
                         ["budgie-control-center", "wifi"])
        self.assertEqual(settings_command("display", tools("gnome-control-center"), GNOME),
                         ["gnome-control-center", "display"])
        self.assertEqual(settings_command("bluetooth", tools("systemsettings"), KDE),
                         ["systemsettings", "kcm_bluetooth"])
        self.assertEqual(settings_command("power", tools("xfce4-settings-manager"), XFCE),
                         ["xfce4-settings-manager"])
        self.assertIsNone(settings_command("wifi", tools(), LXDE))

    def test_monitor_by_desktop(self):
        self.assertEqual(monitor_command(tools("gnome-system-monitor"), GNOME), ["gnome-system-monitor"])
        self.assertEqual(monitor_command(tools("plasma-systemmonitor"), KDE), ["plasma-systemmonitor"])
        self.assertEqual(monitor_command(tools("xfce4-taskmanager"), XFCE), ["xfce4-taskmanager"])
        self.assertEqual(monitor_command(tools(), LXDE), ["x-terminal-emulator", "-e", "top"])


if __name__ == "__main__":
    unittest.main()
