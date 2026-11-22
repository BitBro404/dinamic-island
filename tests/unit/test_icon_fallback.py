"""U1: iconos que no están en todos los temas (Adwaita, Breeze…) caen a uno que sí existe."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.ui.gtk import resolve_icon  # noqa: E402

ADWAITA = {"weather-clear-night-symbolic", "alarm-symbolic", "object-select-symbolic", "view-refresh-symbolic"}


class IconFallbackTest(unittest.TestCase):
    def test_existing_name_is_kept(self):
        self.assertEqual(resolve_icon("alarm-symbolic", ADWAITA.__contains__), "alarm-symbolic")

    def test_missing_name_uses_fallback(self):
        self.assertEqual(resolve_icon("dark-mode-symbolic", ADWAITA.__contains__), "weather-clear-night-symbolic")
        self.assertEqual(resolve_icon("timer-symbolic", ADWAITA.__contains__), "alarm-symbolic")
        self.assertEqual(resolve_icon("emblem-ok-symbolic", ADWAITA.__contains__), "object-select-symbolic")

    def test_unknown_missing_name_is_returned_as_is(self):
        self.assertEqual(resolve_icon("nada-symbolic", ADWAITA.__contains__), "nada-symbolic")

    def test_none_and_empty(self):
        self.assertIsNone(resolve_icon(None, ADWAITA.__contains__))
        self.assertEqual(resolve_icon("", ADWAITA.__contains__), "")


if __name__ == "__main__":
    unittest.main()
