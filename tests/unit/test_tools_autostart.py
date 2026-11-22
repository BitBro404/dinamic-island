"""U6.2/U6.3: entrada de autoarranque, pista para compositores y lanzador con --doctor."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.autostart import autostart_entry, compositor_hint  # noqa: E402
from tools.launcher import launcher_script  # noqa: E402


class InstallTest(unittest.TestCase):
    def test_autostart_uses_real_path(self):
        text = autostart_entry("/home/luis/.local/bin/isla-dinamica")
        self.assertIn("[Desktop Entry]", text)
        self.assertIn("Exec=/home/luis/.local/bin/isla-dinamica", text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        self.assertTrue(text.endswith("\n"))

    def test_compositor_hint_does_not_edit_config(self):
        self.assertEqual(compositor_hint("sway"), "exec isla-dinamica")
        self.assertEqual(compositor_hint("hyprland"), "exec = isla-dinamica")
        self.assertIn("isla-dinamica", compositor_hint("labwc") or "")
        self.assertIsNone(compositor_hint("budgie"))

    def test_launcher_forwards_args(self):
        text = launcher_script("/home/luis/.local/share/isla-dinamica")
        self.assertIn("'/home/luis/.local/share/isla-dinamica'", text)
        self.assertIn("main()", text)
        self.assertIn("isla_dinamica.main", text)


if __name__ == "__main__":
    unittest.main()
