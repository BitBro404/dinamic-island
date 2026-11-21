"""play_sound: un solo lugar para los sonidos (antes estaba repetido en core y en la ventana)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.util import proc  # noqa: E402

BASE = "/usr/share/sounds/freedesktop/stereo/"


class PlaySoundTest(unittest.TestCase):
    def play(self, existing, *names):
        with mock.patch.object(proc.os.path, "exists", side_effect=lambda p: p in existing), \
                mock.patch.object(proc.subprocess, "Popen") as popen:
            proc.play_sound(*names)
        return [c.args[0] for c in popen.call_args_list]

    def test_plays_only_the_first_existing_sound(self):
        calls = self.play({BASE + "complete.oga", BASE + "bell.oga"}, "missing.oga", "complete.oga", "bell.oga")
        self.assertEqual(calls, [["pw-play", BASE + "complete.oga"]])

    def test_nothing_when_no_sound_exists(self):
        self.assertEqual(self.play(set(), "a.oga", "b.oga"), [])

    def test_missing_player_does_not_raise(self):
        with mock.patch.object(proc.os.path, "exists", return_value=True), \
                mock.patch.object(proc.subprocess, "Popen", side_effect=OSError):
            proc.play_sound("complete.oga")


if __name__ == "__main__":
    unittest.main()
