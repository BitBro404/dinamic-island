"""IdleWatch: lectura de las líneas del swayidle propio."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.presence import IdleWatch  # noqa: E402


class IdleParseTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(IdleWatch.parse_line("idle\n"), "idle")
        self.assertEqual(IdleWatch.parse_line("  active  "), "active")
        self.assertIsNone(IdleWatch.parse_line(""))
        self.assertIsNone(IdleWatch.parse_line("swayidle: error\n"))

    def test_command(self):
        self.assertEqual(IdleWatch.command(60),
                         ["swayidle", "-w", "timeout", "60", "echo idle", "resume", "echo active"])


if __name__ == "__main__":
    unittest.main()
