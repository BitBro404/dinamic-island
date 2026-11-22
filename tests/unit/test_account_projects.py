"""Proyectos por cuenta de GitHub: se recuerdan en config.json («account_folders»), se añaden y se quitan, y solo
se vigilan los de la cuenta elegida (más las carpetas globales de «Proyectos»)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos  # noqa: E402
from isla_dinamica import config  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402


class ConfigAccountFoldersTest(unittest.TestCase):
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
        return config.Config().data["account_folders"]

    def test_default_empty(self):
        self.assertEqual(config.Config().data["account_folders"], {})

    def test_round_trip(self):
        c = config.Config()
        c.data["account_folders"] = {"BitBro404": ["~/dinamic island"]}
        c.save()
        self.assertEqual(config.Config().data["account_folders"], {"BitBro404": ["~/dinamic island"]})

    def test_invalid_entries_dropped(self):
        got = self.load({"account_folders": {"BitBro404": ["~/a", "", 3], "mal nombre": ["~/b"], "X": "~/c"}})
        self.assertEqual(got, {"BitBro404": ["~/a"]})
        self.assertEqual(self.load({"account_folders": ["~/a"]}), {})


class FakeConfig:
    def __init__(self):
        self.data = {"git_folders": [], "account_folders": {}}
        self.saved = 0

    def save(self):
        self.saved += 1


def watcher(account="BitBro404"):
    w = gitwatch.GitWatch.__new__(gitwatch.GitWatch)
    w.config, w.on_change, w.enabled = FakeConfig(), lambda: None, lambda: True
    w.account = lambda: account
    w.refreshed = 0
    w.refresh = lambda fetch=False: setattr(w, "refreshed", w.refreshed + 1)
    return w


class AccountFoldersTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b = Repos(), Repos()

    def tearDown(self):
        self.a.cleanup()
        self.b.cleanup()

    def test_add_is_per_account_saved_and_rescans(self):
        w = watcher("BitBro404")
        self.assertIsNone(w.add_account_folder(self.a.work))
        self.assertEqual(w.account_folders(), [gitwatch.short(self.a.work)])
        self.assertEqual(w.account_folders("WM-LuisP"), [])
        self.assertEqual((w.config.saved, w.refreshed), (1, 1))

    def test_errors(self):
        w = watcher()
        self.assertEqual(w.add_account_folder("/no/existe/nada"), "No existe esa carpeta")
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        self.assertEqual(w.add_account_folder(empty.name), "No encontré repos git ahí")
        w.add_account_folder(self.a.work)
        self.assertEqual(w.add_account_folder(self.a.work + "/"), "Ya está en los proyectos de @BitBro404")

    def test_without_account(self):
        self.assertEqual(watcher(None).add_account_folder(self.a.work), "Elige primero una cuenta de GitHub")

    def test_remove(self):
        w = watcher()
        w.add_account_folder(self.a.work)
        w.add_account_folder(self.b.work)
        w.remove_account_folder(gitwatch.short(self.a.work))
        self.assertEqual(w.account_folders(), [gitwatch.short(self.b.work)])
        self.assertEqual(w.config.saved, 3)

    def test_scan_folders_are_global_plus_current_account(self):
        w = watcher("BitBro404")
        w.config.data["git_folders"] = ["~/global"]
        w.config.data["account_folders"] = {"BitBro404": ["~/mio"], "WM-LuisP": ["~/trabajo"]}
        self.assertEqual(w.scan_folders(), (["~/global", "~/mio"], ["~/mio"]))

    def test_scan_marks_repos_of_the_account(self):
        w = watcher()
        w._apply = lambda repos, fetched: setattr(w, "got", repos)
        orig = gitwatch.GLib.idle_add
        gitwatch.GLib.idle_add = lambda fn, *a: fn(*a)
        try:
            w._scan([self.a.work, self.b.work], False, {}, [self.b.work])
        finally:
            gitwatch.GLib.idle_add = orig
        mine = {s["path"]: s["mine"] for s in w.got}
        self.assertEqual(mine, {self.a.work: False, self.b.work: True})


if __name__ == "__main__":
    unittest.main()
