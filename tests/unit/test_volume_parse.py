"""Lectura del volumen de `wpctl get-volume` (texto → valor y silencio)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.media import parse_volume  # noqa: E402


class ParseVolumeTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(parse_volume("Volume: 0.45\n"), (0.45, False))
        self.assertEqual(parse_volume("Volume: 1.00 [MUTED]\n"), (1.0, True))
        self.assertEqual(parse_volume(""), (0.0, False))


if __name__ == "__main__":
    unittest.main()
