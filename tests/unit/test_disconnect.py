"""Desconectar un repo de la isla: deja de vigilarse (sin git automático), se recuerda en config.json
(«git_ignored») y se puede volver a conectar. No se borra nada del disco."""
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
from test_account_projects import watcher  # noqa: E402


class ConfigIgnoredTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = config.CONFIG_PATH
        config.CONFIG_PATH = os.path.join(self.dir.name, "config.json")

    def tearDown(self):
        config.CONFIG_PATH = self.old
        self.dir.cleanup()

    def test_default_and_validation(self):
        self.assertEqual(config.Config().data["git_ignored"], [])
        with open(config.CONFIG_PATH, "w") as f:
            json.dump({"git_ignored": ["/home/u/web", "", 3, "relativa", "/home/u/web", "~/api"]}, f)
        self.assertEqual(config.Config().data["git_ignored"], ["/home/u/web", os.path.expanduser("~/api")])


def scan(w, folders, mine=()):
    w._apply = lambda repos, fetched: setattr(w, "got", repos)
    orig = gitwatch.GLib.idle_add
    gitwatch.GLib.idle_add = lambda fn, *a: fn(*a)
    try:
        w._scan(folders, False, {}, list(mine))
    finally:
        gitwatch.GLib.idle_add = orig
    return sorted(s["path"] for s in w.got)


class DisconnectTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b = Repos(), Repos()
        self.addCleanup(self.a.cleanup)
        self.addCleanup(self.b.cleanup)
        self.w = watcher()
        self.w.config.data["git_ignored"] = []
        self.w.repos = [{"path": self.a.work}, {"path": self.b.work}]

    def test_disconnect_hides_it_now_remembers_it_and_rescans(self):
        self.w.disconnect(self.a.work + "/")
        self.assertEqual(self.w.ignored, [self.a.work])
        self.assertEqual([s["path"] for s in self.w.repos], [self.b.work])     # deja de verse al momento
        self.assertEqual((self.w.config.saved, self.w.refreshed), (1, 1))
        self.w.disconnect(self.a.work)                                         # repetido: no se duplica
        self.assertEqual(self.w.ignored, [self.a.work])

    def test_scan_skips_disconnected_repos_even_inside_a_watched_folder(self):
        parent = os.path.dirname(self.a.work)          # la carpeta vigilada contiene «work» (y «remote.git»)
        self.assertEqual(scan(self.w, [parent]), [self.a.work])
        self.w.disconnect(self.a.work)
        self.assertEqual(scan(self.w, [parent]), [])
        self.assertEqual(scan(self.w, [self.b.work]), [self.b.work])           # los demás siguen

    def test_reconnect(self):
        self.w.disconnect(self.a.work)
        self.w.reconnect(self.a.work)
        self.assertEqual(self.w.ignored, [])
        self.assertEqual(scan(self.w, [self.a.work]), [self.a.work])

    def test_nothing_is_deleted_from_disk(self):
        self.w.disconnect(self.a.work)
        self.assertTrue(os.path.isdir(os.path.join(self.a.work, ".git")))


if __name__ == "__main__":
    unittest.main()
