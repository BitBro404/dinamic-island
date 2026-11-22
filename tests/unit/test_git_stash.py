"""Stash por repo: lista con rama, mensaje y fecha; aplicar (pop) y borrar comprobando que es el mismo stash."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos, git  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402

US = "\x1f"


def write(repo, name, text):
    with open(os.path.join(repo, name), "w") as f:
        f.write(text)


class ParseStashesTest(unittest.TestCase):
    def test_parse(self):
        out = "\n".join(US.join(x) for x in (
            ("stash@{0}", "a" * 40, "On feat: arreglo a medias", "1700000100"),
            ("stash@{1}", "b" * 40, "WIP on main: 1a2b3c4 inicio", "1700000000"),
            ("stash@{2}", "c" * 40, "algo raro", "x"),
        ))
        got = gitwatch.parse_stashes(out)
        self.assertEqual([(s["ref"], s["branch"], s["msg"], s["ts"]) for s in got],
                         [("stash@{0}", "feat", "arreglo a medias", 1700000100),
                          ("stash@{1}", "main", "1a2b3c4 inicio", 1700000000),
                          ("stash@{2}", None, "algo raro", None)])
        self.assertEqual(got[0]["sha"], "a" * 40)


class StashOpsTest(unittest.TestCase):
    def setUp(self):
        self.r = Repos()
        w = self.r.work
        write(w, "a.txt", "uno")
        git(w, "stash", "push", "-q", "-m", "primero")
        write(w, "a.txt", "dos")
        git(w, "stash", "push", "-q", "-m", "segundo")

    def tearDown(self):
        self.r.cleanup()

    def stashes(self):
        return gitwatch.repo_status(self.r.work)["stashes"]

    def test_status_lists_stashes_newest_first(self):
        st = self.stashes()
        self.assertEqual([(s["ref"], s["branch"], s["msg"]) for s in st],
                         [("stash@{0}", "main", "segundo"), ("stash@{1}", "main", "primero")])
        self.assertEqual(gitwatch.repo_status(self.r.work)["stash"], 2)

    def test_pop_applies_and_removes(self):
        s = self.stashes()[1]
        ok, msg = gitwatch.run_op(self.r.work, "stash_pop", ref=s["ref"], sha=s["sha"])
        self.assertTrue(ok, msg)
        with open(os.path.join(self.r.work, "a.txt")) as f:
            self.assertEqual(f.read(), "uno")
        self.assertEqual([x["msg"] for x in self.stashes()], ["segundo"])

    def test_drop_removes_only_that_one(self):
        s = self.stashes()[0]
        ok, msg = gitwatch.run_op(self.r.work, "stash_drop", ref=s["ref"], sha=s["sha"])
        self.assertTrue(ok, msg)
        self.assertEqual([x["msg"] for x in self.stashes()], ["primero"])

    def test_refuses_if_the_list_changed(self):
        old = self.stashes()[0]                     # «segundo» en stash@{0}
        write(self.r.work, "a.txt", "tres")
        git(self.r.work, "stash", "push", "-q", "-m", "tercero")   # ahora stash@{0} es otro
        for kind in ("stash_drop", "stash_pop"):
            ok, msg = gitwatch.run_op(self.r.work, kind, ref=old["ref"], sha=old["sha"])
            self.assertFalse(ok)
            self.assertIn("cambió", msg)
        self.assertEqual(len(self.stashes()), 3)


if __name__ == "__main__":
    unittest.main()
