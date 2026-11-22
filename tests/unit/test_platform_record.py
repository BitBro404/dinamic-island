"""U4.3: grabar con wf-recorder, ffmpeg x11grab, extensión GNOME o portal; ocultar si no hay método."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.chain import Tools, pick  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402
from isla_dinamica.platform.record import METHODS, audio_argv, build, geometry, to_ffmpeg  # noqa: E402
from isla_dinamica.pages.registry import tool, visible  # noqa: E402

WLR = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "sway"})
X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})
GNOME = detect({"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "w", "XDG_CURRENT_DESKTOP": "GNOME"})

GEOM = "100,20 800x600"


def tools(cmds=(), names=()):
    return Tools(which=lambda c: c if c in cmds else None, has_name=lambda n: n in names)


class RecordTest(unittest.TestCase):
    def test_chain_by_desktop(self):
        self.assertEqual(pick(METHODS, tools(cmds={"wf-recorder"}), WLR).name, "wf-recorder")
        self.assertEqual(pick(METHODS, tools(cmds={"ffmpeg"}), X11).name, "ffmpeg (X11)")
        self.assertEqual(pick(METHODS, tools(names={"io.github.bitbro404.IslaDinamica.Shell"}), GNOME).name,
                         "GNOME Shell (extensión)")
        self.assertEqual(pick(METHODS, tools(), detect({"XDG_SESSION_TYPE": "unknown"})).name, "portal")

    def test_geometry_helpers(self):
        self.assertEqual(geometry(GEOM), (":0+100+20", "800x600"))
        self.assertEqual(to_ffmpeg(GEOM), (":0+100,20", "800x600"))

    def test_wf_recorder_argv(self):
        m = pick(METHODS, tools(cmds={"wf-recorder"}), WLR)
        argv = build(m, GEOM, "/tmp/v.mp4", audio_device="default")
        self.assertEqual(argv[:5], ["wf-recorder", "-y", "-g", GEOM, "-f"])
        self.assertIn("--audio=default", argv)

    def test_ffmpeg_argv_with_area_and_pulse(self):
        m = pick(METHODS, tools(cmds={"ffmpeg"}), X11)
        argv = build(m, GEOM, "/tmp/v.mp4", audio_device="default", display=":1")
        self.assertEqual(argv[:7], ["ffmpeg", "-y", "-f", "x11grab", "-video_size", "800x600", "-framerate"])
        self.assertIn(":1+100,20", argv)
        self.assertIn("-f", argv)
        self.assertIn("pulse", argv)
        self.assertIn("default", argv)
        self.assertTrue(argv[-1].endswith(".mp4"))

    def test_ffmpeg_without_audio(self):
        m = pick(METHODS, tools(cmds={"ffmpeg"}), X11)
        argv = build(m, None, "/tmp/v.mp4")
        self.assertNotIn("pulse", argv)
        self.assertNotIn("-video_size", argv)

    def test_audio_argv(self):
        self.assertEqual(audio_argv("default"), ["-f", "pulse", "-i", "default"])
        self.assertEqual(audio_argv(None), [])

    def test_tool_hidden_without_method(self):
        t = tool("media-record-symbolic", "Grabar", "Grabar", "record",
                 available=lambda core: core.recorder.available)

        class Core:
            class recorder:
                available = False

        class CoreOk(Core):
            class recorder:
                available = True

        self.assertFalse(visible(t, Core()))
        self.assertTrue(visible(t, CoreOk()))


if __name__ == "__main__":
    unittest.main()
