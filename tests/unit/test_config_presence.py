"""Preferencias del sensor de presencia en config.json."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import common  # noqa: E402

DEFAULT = {"minutes": 5, "warn": 30, "paused_until": 0, "start": "08:00", "end": "18:00", "days": [0, 1, 2, 3, 4]}


class ConfigPresenceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = common.CONFIG_PATH
        common.CONFIG_PATH = os.path.join(self.dir.name, "config.json")

    def tearDown(self):
        common.CONFIG_PATH = self.old
        self.dir.cleanup()

    def load(self, data=None):
        if data is not None:
            with open(common.CONFIG_PATH, "w") as f:
                json.dump(data, f)
        return common.Config().data["presence"]

    def test_defaults_without_file(self):
        self.assertEqual(self.load(), DEFAULT)

    def test_defaults_when_missing(self):
        self.assertEqual(self.load({"city": "Bogota"}), DEFAULT)

    def test_valid_values_kept(self):
        got = self.load({"presence": {"minutes": 10, "paused_until": 12345.5, "start": "22:00", "end": "02:30",
                                      "days": [4, 5]}})
        self.assertEqual(got["minutes"], 10)
        self.assertEqual(got["paused_until"], 12345.5)
        self.assertEqual((got["start"], got["end"], got["days"]), ("22:00", "02:30", [4, 5]))

    def test_invalid_values_use_default(self):
        got = self.load({"presence": {"minutes": "x", "warn": -3, "start": "25:00", "end": "8", "days": [9, 1, 1],
                                      "otra": 1}})
        self.assertEqual(got, DEFAULT)

    def test_minutes_range(self):
        self.assertEqual(self.load({"presence": {"minutes": 0}})["minutes"], 5)
        self.assertEqual(self.load({"presence": {"minutes": 61}})["minutes"], 5)
        self.assertEqual(self.load({"presence": {"minutes": True}})["minutes"], 5)

    def test_empty_days_allowed(self):
        self.assertEqual(self.load({"presence": {"days": []}})["days"], [])

    def test_feature_off_by_default(self):
        self.assertFalse(common.Config().data["features"].get("presence", common.FEATURE_DEFAULTS["presence"]))


if __name__ == "__main__":
    unittest.main()
