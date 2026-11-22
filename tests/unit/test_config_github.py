"""La cuenta de GitHub elegida en la isla se recuerda al reiniciar (config.json → «github_account»)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import config  # noqa: E402


class ConfigGitHubAccountTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = config.CONFIG_PATH
        config.CONFIG_PATH = os.path.join(self.dir.name, "config.json")

    def tearDown(self):
        config.CONFIG_PATH = self.old
        self.dir.cleanup()

    def load(self, data):
        with open(config.CONFIG_PATH, "w") as f:
            json.dump(data, f)
        return config.Config().data.get("github_account")

    def test_saved_account_survives_restart(self):
        self.assertEqual(self.load({"github_account": "BitBro404"}), "BitBro404")

    def test_round_trip(self):
        c = config.Config()
        c.data["github_account"] = "WM-LuisP"
        c.save()
        self.assertEqual(config.Config().data["github_account"], "WM-LuisP")

    def test_invalid_values_ignored(self):
        for bad in (None, 3, "", "con espacio", "a/b", ["x"]):
            self.assertIsNone(self.load({"github_account": bad}), bad)


if __name__ == "__main__":
    unittest.main()
