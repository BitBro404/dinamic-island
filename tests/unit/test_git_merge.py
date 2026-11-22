"""Crear ramas desde otra, merge a la rama actual, conflictos, cancelar y terminar el merge (repos temporales)."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos, commit, git  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402


class GitTestEnv(unittest.TestCase):
    """git de la isla con una config global temporal: sin firma GPG y con autor (el merge crea commits)."""
    def setUp(self):
        self.cfgdir = tempfile.TemporaryDirectory()
        cfg = os.path.join(self.cfgdir.name, "gitconfig")
        with open(cfg, "w") as f:
            f.write("[user]\n\tname = Prueba\n\temail = prueba@example.invalid\n[commit]\n\tgpgsign = false\n")
        p = mock.patch.object(gitwatch, "GIT_ENV", dict(gitwatch.GIT_ENV, GIT_CONFIG_GLOBAL=cfg, GIT_EDITOR="true"))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.cfgdir.cleanup)
        self.r = Repos()
        self.addCleanup(self.r.cleanup)
        self.w = self.r.work

    def status(self):
        return gitwatch.repo_status(self.w)


class CreateBranchTest(GitTestEnv):
    def test_create_and_switch(self):
        ok, msg = gitwatch.run_op(self.w, "create", name="feat/nueva", base="main")
        self.assertTrue(ok, msg)
        self.assertEqual(self.status()["branch"], "feat/nueva")
        self.assertIn("feat/nueva", msg)

    def test_create_without_switching(self):
        ok, _ = gitwatch.run_op(self.w, "create", name="otra", base="main", switch=False)
        self.assertTrue(ok)
        self.assertEqual(self.status()["branch"], "main")
        self.assertIn("otra", [b["name"] for b in gitwatch.list_branches(self.w)])

    def test_create_from_remote_branch(self):
        git(self.w, "switch", "-q", "-c", "devel")
        commit(self.w, "d.txt", msg="devel")
        git(self.w, "push", "-q", "origin", "devel")
        git(self.w, "switch", "-q", "main")
        git(self.w, "branch", "-q", "-D", "devel")
        ok, msg = gitwatch.run_op(self.w, "create", name="desde-devel", base="devel", base_remote=True)
        self.assertTrue(ok, msg)
        self.assertTrue(os.path.exists(os.path.join(self.w, "d.txt")))

    def test_invalid_or_existing_name(self):
        self.assertEqual(gitwatch.run_op(self.w, "create", name="mal nombre", base="main"),
                         (False, "Nombre de rama no válido: mal nombre"))
        self.assertEqual(gitwatch.run_op(self.w, "create", name="main", base="main"),
                         (False, "Ya existe la rama main"))
        self.assertEqual(gitwatch.run_op(self.w, "create", name="", base="main"),
                         (False, "Escribe el nombre de la rama nueva"))

    def test_switching_blocked_with_changes(self):
        open(os.path.join(self.w, "suelto.txt"), "w").close()
        self.assertEqual(gitwatch.run_op(self.w, "create", name="x", base="main"),
                         (False, gitwatch.BLOCK_SWITCH))
        self.assertTrue(gitwatch.run_op(self.w, "create", name="x", base="main", switch=False)[0])


class MergeTest(GitTestEnv):
    def branch_editing(self, name, text):
        git(self.w, "switch", "-q", "-c", name)
        commit(self.w, "a.txt", text, msg=f"{name} edita a.txt")
        git(self.w, "switch", "-q", "main")

    def test_clean_merge(self):
        git(self.w, "switch", "-q", "-c", "feat")
        commit(self.w, "f.txt", msg="feat")
        git(self.w, "switch", "-q", "main")
        commit(self.w, "m.txt", msg="main avanza")
        ok, msg = gitwatch.run_op(self.w, "merge", branch="feat")
        self.assertTrue(ok, msg)
        self.assertEqual(msg, "Fusionada feat en main")
        self.assertTrue(os.path.exists(os.path.join(self.w, "f.txt")))
        self.assertFalse(self.status()["merging"])

    def test_conflict_leaves_merge_in_progress_with_files(self):
        self.branch_editing("feat", "de feat")
        commit(self.w, "a.txt", "de main", msg="main edita a.txt")
        ok, msg = gitwatch.run_op(self.w, "merge", branch="feat")
        self.assertFalse(ok)
        self.assertEqual(msg, "Conflictos en 1 archivo: a.txt")
        s = self.status()
        self.assertTrue(s["merging"])
        self.assertEqual(s["conflict_files"], ["a.txt"])

    def test_abort(self):
        self.branch_editing("feat", "de feat")
        commit(self.w, "a.txt", "de main", msg="main edita a.txt")
        gitwatch.run_op(self.w, "merge", branch="feat")
        ok, msg = gitwatch.run_op(self.w, "merge_abort")
        self.assertTrue(ok, msg)
        s = self.status()
        self.assertFalse(s["merging"])
        with open(os.path.join(self.w, "a.txt")) as f:
            self.assertEqual(f.read(), "de main")

    def test_finish_only_when_resolved(self):
        self.branch_editing("feat", "de feat")
        commit(self.w, "a.txt", "de main", msg="main edita a.txt")
        gitwatch.run_op(self.w, "merge", branch="feat")
        self.assertEqual(gitwatch.run_op(self.w, "merge_finish"),
                         (False, "Aún hay 1 archivo en conflicto: a.txt"))
        with open(os.path.join(self.w, "a.txt"), "w") as f:
            f.write("las dos cosas")
        git(self.w, "add", "a.txt")
        ok, msg = gitwatch.run_op(self.w, "merge_finish")
        self.assertTrue(ok, msg)
        self.assertFalse(self.status()["merging"])

    def test_merge_source_names_the_incoming_branch(self):
        self.assertEqual(gitwatch.parse_merge_msg("Merge branch 'feat/x'\n\n# Conflicts:\n"), "feat/x")
        self.assertEqual(gitwatch.parse_merge_msg("Merge remote-tracking branch 'origin/devel' into main"),
                         "origin/devel")
        self.assertIsNone(gitwatch.parse_merge_msg("otra cosa"))
        self.branch_editing("feat", "de feat")
        commit(self.w, "a.txt", "de main", msg="main edita a.txt")
        gitwatch.run_op(self.w, "merge", branch="feat")
        self.assertEqual(self.status()["merge_from"], "feat")

    def test_merge_blocked_with_changes(self):
        self.branch_editing("feat", "de feat")
        with open(os.path.join(self.w, "a.txt"), "w") as f:
            f.write("sin commit")
        self.assertEqual(gitwatch.run_op(self.w, "merge", branch="feat"),
                         (False, "Haz commit o descarta los cambios antes del merge"))


if __name__ == "__main__":
    unittest.main()
