"""Burbuja Bluetooth: el interruptor existe en «Más» y viene activado por defecto."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import config  # noqa: E402
from isla_dinamica.pages import bluetooth  # noqa: F401,E402  (al importarse registra la función)
from isla_dinamica.pages.registry import FEATURES  # noqa: E402


class BluetoothFeatureTest(unittest.TestCase):
    def test_registered_in_more(self):
        entries = [f for f in FEATURES if f["key"] == "bt_bubble"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Burbuja Bluetooth")
        self.assertTrue(entries[0]["desc"])

    def test_enabled_by_default(self):
        self.assertTrue(config.FEATURE_DEFAULTS.get("bt_bubble", True))


if __name__ == "__main__":
    unittest.main()
