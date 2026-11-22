"""U5.1: modo oscuro y luz nocturna por gsettings/comando, con portal para leer el oscuro."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.appearance import (DARK_METHODS, NIGHT_METHODS, Appearance,  # noqa: E402
                                               SettingsAppearance, parse_color_scheme, portal_color_scheme)
from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

BUDGIE = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "Budgie"})
KDE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"})
X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "LXDE"})


def tools(cmds=(), schemas=()):
    return Tools(which=lambda c: c if c in cmds else None, has_schema=lambda s: s in schemas)


class FakeSettings:
    def __init__(self, schema, values):
        self.schema, self.values, self.cbs = schema, dict(values), []

    def get_string(self, key):
        return self.values.get(key, "")

    def get_boolean(self, key):
        return bool(self.values.get(key, False))

    def set_string(self, key, value):
        self.values[key] = value

    def set_boolean(self, key, value):
        self.values[key] = value

    def connect(self, sig, cb):
        self.cbs.append(cb)

    def changed(self):
        for cb in self.cbs:
            cb()


class FakeBus:
    def __init__(self, value=1):
        self.value = value

    def call_sync(self, *_args):
        class R:
            def unpack(self_inner):
                return (self.value,)
        return R()


class AppearanceTest(unittest.TestCase):
    def test_dark_chain(self):
        self.assertEqual(pick(DARK_METHODS, tools(schemas={"org.gnome.desktop.interface"}), BUDGIE).name,
                         "GNOME color-scheme")
        self.assertEqual(pick(DARK_METHODS, tools(cmds={"kwriteconfig6", "qdbus6"}), KDE).name,
                         "KDE ColorScheme")
        self.assertEqual(pick(DARK_METHODS, tools(), X11).name, "portal (solo lectura)")

    def test_night_chain(self):
        self.assertEqual(pick(NIGHT_METHODS, tools(schemas={"org.gnome.settings-daemon.plugins.color"}), BUDGIE).name,
                         "GNOME night light")
        self.assertEqual(pick(NIGHT_METHODS, tools(cmds={"gammastep"}), X11).name, "gammastep")
        self.assertIsNone(pick(NIGHT_METHODS, tools(), X11))

    def test_portal_color_scheme(self):
        self.assertTrue(parse_color_scheme(1))
        self.assertFalse(parse_color_scheme(0))
        self.assertFalse(parse_color_scheme(2))
        self.assertFalse(portal_color_scheme(FakeBus(0)))
        self.assertTrue(portal_color_scheme(FakeBus(1)))

    def test_settings_adapter(self):
        s = FakeSettings("org.gnome.desktop.interface", {"color-scheme": "default"})
        a = SettingsAppearance(lambda schema: s, "org.gnome.desktop.interface", "color-scheme")
        self.assertFalse(a.get())
        changes = []
        a.watch(lambda: changes.append(1))
        a.set(True)
        s.changed()
        self.assertTrue(a.get())
        self.assertEqual(s.values["color-scheme"], "prefer-dark")
        self.assertEqual(changes, [1])

    def test_appearance_delegates_and_reports_support(self):
        changes = []
        ap = Appearance(lambda: changes.append(1), tools=tools(schemas={"org.gnome.desktop.interface"}),
                        desktop=BUDGIE, settings=lambda schema: FakeSettings(schema, {"color-scheme": "default"}))
        self.assertTrue(ap.has_dark)
        self.assertFalse(ap.has_night)
        self.assertFalse(ap.dark)
        ap.toggle_dark()
        s = ap._dark.s
        s.changed()
        self.assertTrue(ap.dark)
        self.assertEqual(changes, [1])
        self.assertFalse(ap.toggle_night())


if __name__ == "__main__":
    unittest.main()
