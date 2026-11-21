"""S1: la contraseña del Wi-Fi nunca va en la línea de comandos (se vería con `ps`)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.network import wifi_connect_command  # noqa: E402

NET = {"ssid": "Casa", "secure": True}


class WifiCommandTest(unittest.TestCase):
    def test_password_goes_by_stdin_not_argv(self):
        argv, stdin = wifi_connect_command(NET, "s3cr3t-pass", known=set())
        self.assertNotIn("s3cr3t-pass", " ".join(argv))
        self.assertNotIn("password", argv)
        self.assertIn("--ask", argv)
        self.assertEqual(stdin, "s3cr3t-pass\n")
        self.assertEqual(argv[-1], "Casa")

    def test_known_network_without_password(self):
        argv, stdin = wifi_connect_command(NET, None, known={"Casa"})
        self.assertEqual(argv, ["nmcli", "connection", "up", "id", "Casa"])
        self.assertIsNone(stdin)

    def test_open_network(self):
        argv, stdin = wifi_connect_command({"ssid": "Libre", "secure": False}, None, known=set())
        self.assertEqual(argv, ["nmcli", "device", "wifi", "connect", "Libre"])
        self.assertIsNone(stdin)

    def test_secure_unknown_without_password_needs_one(self):
        self.assertIsNone(wifi_connect_command(NET, None, known=set()))


if __name__ == "__main__":
    unittest.main()
