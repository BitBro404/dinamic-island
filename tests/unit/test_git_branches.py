"""Ramas por repo: listar locales y remotas, cambiar (bloqueado con cambios sin commit)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos, commit, git  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402

US = "\x1f"


class ParseBranchesTest(unittest.TestCase):
    def test_locals_first_then_remote_only_without_current_head_or_duplicates(self):
        out = "\n".join(US.join(x) for x in (
            ("refs/heads/main", "300", "inicio"),
            ("refs/heads/feat/login", "200", "login"),
            ("refs/remotes/origin/HEAD", "300", "inicio"),
            ("refs/remotes/origin/main", "300", "inicio"),
            ("refs/remotes/origin/feat/login", "200", "login"),
            ("refs/remotes/origin/devel", "250", "devel"),
        ))
        got = gitwatch.parse_branches(out, current="main")
        self.assertEqual([(b["name"], b["remote"]) for b in got], [("feat/login", False), ("devel", True)])
        self.assertEqual((got[0]["ts"], got[0]["subject"]), (200, "login"))


class BranchOpsTest(unittest.TestCase):
    def setUp(self):
        self.r = Repos()
        w = self.r.work
        git(w, "switch", "-q", "-c", "feat")
        commit(w, "f.txt", msg="feat")
        git(w, "switch", "-q", "main")
        # «devel» solo existe en el remoto
        git(w, "switch", "-q", "-c", "devel")
        commit(w, "d.txt", msg="devel")
        git(w, "push", "-q", "origin", "devel")
        git(w, "switch", "-q", "main")
        git(w, "branch", "-q", "-D", "devel")

    def tearDown(self):
        self.r.cleanup()

    def test_list_branches(self):
        names = [(b["name"], b["remote"]) for b in gitwatch.list_branches(self.r.work)]
        self.assertEqual(sorted(names), [("devel", True), ("feat", False)])

    def test_switch_to_local_branch(self):
        ok, msg = gitwatch.run_op(self.r.work, "switch", branch="feat")
        self.assertTrue(ok, msg)
        self.assertEqual(gitwatch.repo_status(self.r.work)["branch"], "feat")

    def test_switch_to_remote_only_branch_creates_tracking_branch(self):
        ok, msg = gitwatch.run_op(self.r.work, "switch", branch="devel", remote=True)
        self.assertTrue(ok, msg)
        s = gitwatch.repo_status(self.r.work)
        self.assertEqual((s["branch"], s["upstream"]), ("devel", "origin/devel"))

    def test_switch_blocked_with_uncommitted_changes(self):
        with open(os.path.join(self.r.work, "a.txt"), "w") as f:
            f.write("cambio sin commit")
        ok, msg = gitwatch.run_op(self.r.work, "switch", branch="feat")
        self.assertFalse(ok)
        self.assertIn("Haz commit o descarta los cambios", msg)
        self.assertEqual(gitwatch.repo_status(self.r.work)["branch"], "main")

    def test_switch_blocked_with_untracked_files(self):
        open(os.path.join(self.r.work, "nuevo.txt"), "w").close()
        ok, _ = gitwatch.run_op(self.r.work, "switch", branch="feat")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
