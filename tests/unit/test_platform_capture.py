"""U4.2: capturas con grim, spectacle, maim, scrot, extensión GNOME o portal (argv por método)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.capture import METHODS, build, image_copy_argv, to_maim, to_scrot  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

WLR = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"})
KDE = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "KDE"})
X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})

GEOM = "100,20 800x600"


def tools(cmds=(), names=()):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names)


class CaptureTest(unittest.TestCase):
    def test_chain_by_desktop(self):
        self.assertEqual(pick(METHODS, tools(cmds={"grim", "slurp"}), WLR).name, "grim + slurp")
        self.assertEqual(pick(METHODS, tools(cmds={"spectacle"}), KDE).name, "spectacle")
        self.assertEqual(pick(METHODS, tools(cmds={"maim"}), X11).name, "maim")
        self.assertEqual(pick(METHODS, tools(cmds={"scrot"}), X11).name, "scrot")
        self.assertEqual(pick(METHODS, tools(names={"io.github.bitbro404.IslaDinamica.Shell"}), GNOME).name,
                         "GNOME Shell (extensión)")
        self.assertEqual(pick(METHODS, tools(), GNOME).name, "portal")

    def test_argv_builders(self):
        self.assertEqual(build(pick(METHODS, tools(cmds={"grim", "slurp"}), WLR), GEOM, "/tmp/c.png"),
                         ["grim", "-g", GEOM, "/tmp/c.png"])
        self.assertEqual(build(pick(METHODS, tools(cmds={"maim"}), X11), GEOM, "/tmp/c.png"),
                         ["maim", "-g", "800x600+100+20", "/tmp/c.png"])
        self.assertEqual(build(pick(METHODS, tools(cmds={"scrot"}), X11), GEOM, "/tmp/c.png"),
                         ["scrot", "-a", "100,20,800,600", "/tmp/c.png"])
        self.assertEqual(build(pick(METHODS, tools(cmds={"spectacle"}), KDE), None, "/tmp/c.png"),
                         ["spectacle", "-b", "-f", "-o", "/tmp/c.png"])

    def test_geometry_conversions(self):
        self.assertEqual(to_maim(GEOM), "800x600+100+20")
        self.assertEqual(to_scrot(GEOM), "100,20,800,600")

    def test_copy_image_argv(self):
        self.assertEqual(image_copy_argv("/tmp/c.png", tools(cmds={"wl-copy"}), WLR),
                         ["wl-copy", "-t", "image/png"])
        self.assertEqual(image_copy_argv("/tmp/c.png", tools(cmds={"xclip"}), X11),
                         ["xclip", "-selection", "clipboard", "-t", "image/png"])


if __name__ == "__main__":
    unittest.main()
