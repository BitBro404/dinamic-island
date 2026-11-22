"""U5.4: volumen con wpctl o pactl y avisos sonoros con pw-play/paplay/canberra."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.platform.audio import (parse_volume, play_argv, read_command,  # noqa: E402
                                          set_argv, step_argv, toggle_mute_argv)
from isla_dinamica.platform.chain import Tools  # noqa: E402
from isla_dinamica.platform.desktop import detect  # noqa: E402

X11 = detect({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"})


def tools(*cmds):
    return Tools(which=lambda c: c if c in cmds else None)


class AudioTest(unittest.TestCase):
    def test_parse_wpctl(self):
        self.assertEqual(parse_volume("Volume: 0.45 [MUTED]"), (0.45, True))
        self.assertEqual(parse_volume("Volume: 0.8"), (0.8, False))

    def test_parse_pactl(self):
        out = "Volume: front-left: 29330 /  45% / -21.00 dB,   front-right: 29330 /  45% / -21.00 dB\nMute: yes"
        self.assertEqual(parse_volume(out), (0.45, True))
        self.assertEqual(parse_volume("Mute: no\nVolume: 100%"), (1.0, False))

    def test_volume_command_fallback(self):
        self.assertEqual(read_command(tools("wpctl")), ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        self.assertEqual(read_command(tools("pactl")), ["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        self.assertIsNone(read_command(tools()))

    def test_volume_actions(self):
        self.assertEqual(step_argv(True, tools("wpctl")),
                         ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+"])
        self.assertEqual(set_argv(0.3, tools("pactl")), ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "30%"])
        self.assertEqual(toggle_mute_argv(tools("wpctl")),
                         ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])

    def test_sound_command_chain(self):
        self.assertEqual(play_argv("/tmp/a.oga", tools("pw-play")), ["pw-play", "/tmp/a.oga"])
        self.assertEqual(play_argv("/tmp/a.oga", tools("paplay")), ["paplay", "/tmp/a.oga"])
        self.assertEqual(play_argv("/tmp/a.oga", tools("canberra-gtk-play")),
                         ["canberra-gtk-play", "-f", "/tmp/a.oga"])
        self.assertIsNone(play_argv("/tmp/a.oga", tools(), X11))


if __name__ == "__main__":
    unittest.main()
