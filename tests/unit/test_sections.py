"""Secciones plegables de la pestaña GitHub: contador de novedades del día y estado guardado."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import config  # noqa: E402
from isla_dinamica.util import fmt  # noqa: E402

NOW = datetime(2026, 11, 21, 15, 0).timestamp()
MIDNIGHT = datetime(2026, 11, 21, 0, 0).timestamp()


class TodayCountTest(unittest.TestCase):
    def test_counts_only_since_local_midnight(self):
        ts = [NOW - 60, MIDNIGHT, MIDNIGHT - 1, NOW - 86400, None, 0]
        self.assertEqual(fmt.today_count(ts, NOW), 2)

    def test_empty(self):
        self.assertEqual(fmt.today_count([], NOW), 0)


class CollapsedConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = config.CONFIG_PATH
        config.CONFIG_PATH = os.path.join(self.dir.name, "config.json")

    def tearDown(self):
        config.CONFIG_PATH = self.old
        self.dir.cleanup()

    def load(self, data=None):
        if data is not None:
            with open(config.CONFIG_PATH, "w") as f:
                json.dump(data, f)
        return config.Config().data["collapsed"]

    def test_default_nothing_collapsed(self):
        self.assertEqual(self.load(), [])

    def test_keeps_only_strings(self):
        self.assertEqual(self.load({"collapsed": ["gh_merged", 3, None, "dp_recent"]}), ["gh_merged", "dp_recent"])

    def test_bad_type_ignored(self):
        self.assertEqual(self.load({"collapsed": "gh_merged"}), [])


if __name__ == "__main__":
    unittest.main()
