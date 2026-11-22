"""U0.2: cadenas de métodos — el primero disponible gana, sin fallar si no hay ninguno."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Method, Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

KDE = detect({"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w"})


def fake_tools(cmds=(), names=(), schemas=()):
    return Tools(which=lambda c: f"/usr/bin/{c}" if c in cmds else None,
                 has_name=lambda n: n in names, has_schema=lambda s: s in schemas)


def boom(_t, _d):
    raise RuntimeError("roto")


class ChainTest(unittest.TestCase):
    def test_first_available_wins(self):
        chain = [Method("a", lambda t, d: t.has("aa")), Method("b", lambda t, d: t.has("bb")),
                 Method("c", lambda t, d: True)]
        self.assertEqual(pick(chain, fake_tools(cmds={"bb"}), KDE).name, "b")

    def test_none_when_nothing_available(self):
        self.assertIsNone(pick([Method("a", lambda t, d: t.has("aa"))], fake_tools(), KDE))

    def test_broken_check_is_skipped(self):
        self.assertEqual(pick([Method("x", boom), Method("y", lambda t, d: True)], fake_tools(), KDE).name, "y")

    def test_has_needs_every_command(self):
        t = fake_tools(cmds={"grim"})
        self.assertFalse(t.has("grim", "slurp"))
        self.assertTrue(t.has("grim"))

    def test_desktop_condition(self):
        chain = [Method("gnome", lambda t, d: d.family == "gnome"), Method("kde", lambda t, d: d.family == "kde")]
        self.assertEqual(pick(chain, fake_tools(), KDE).name, "kde")

    def test_bus_names_and_schemas(self):
        t = fake_tools(names={"org.kde.KWin"}, schemas={"org.gnome.desktop.interface"})
        self.assertTrue(t.has_name("org.kde.KWin"))
        self.assertFalse(t.has_name("org.gnome.Shell"))
        self.assertTrue(t.has_schema("org.gnome.desktop.interface"))


if __name__ == "__main__":
    unittest.main()
