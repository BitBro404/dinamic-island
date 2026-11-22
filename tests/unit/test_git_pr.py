"""PR de una rama a otra: URL de comparar de GitHub y avisos si la rama de origen no está subida o al día."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos, commit, git  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402


class CompareUrlTest(unittest.TestCase):
    def test_url(self):
        self.assertEqual(gitwatch.compare_url("o/r", "main", "feat/login"),
                         "https://github.com/o/r/compare/main...feat/login?expand=1")

    def test_names_are_encoded(self):
        self.assertEqual(gitwatch.compare_url("o/r", "main", "fix #2 ñ"),
                         "https://github.com/o/r/compare/main...fix%20%232%20%C3%B1?expand=1")


class PrCheckTest(unittest.TestCase):
    def setUp(self):
        self.r = Repos()
        git(self.r.work, "switch", "-q", "-c", "feat")
        commit(self.r.work, "f.txt", msg="feat")

    def tearDown(self):
        self.r.cleanup()

    def test_default_branch_is_origin_head(self):
        self.assertEqual(gitwatch.default_branch(self.r.work), "main")

    def test_branch_not_pushed(self):
        self.assertEqual(gitwatch.pr_check(self.r.work, "main", "feat"), "Sube la rama feat primero")

    def test_branch_with_unpushed_commits(self):
        git(self.r.work, "push", "-q", "-u", "origin", "feat")
        commit(self.r.work, "g.txt", msg="otro")
        commit(self.r.work, "h.txt", msg="otro más")
        self.assertEqual(gitwatch.pr_check(self.r.work, "main", "feat"),
                         "La rama feat tiene 2 commits sin subir: súbelos primero")

    def test_pushed_and_up_to_date_is_ok(self):
        git(self.r.work, "push", "-q", "-u", "origin", "feat")
        self.assertIsNone(gitwatch.pr_check(self.r.work, "main", "feat"))

    def test_same_branch(self):
        self.assertEqual(gitwatch.pr_check(self.r.work, "main", "main"), "Elige dos ramas distintas")

    def test_base_must_exist_in_remote(self):
        git(self.r.work, "push", "-q", "-u", "origin", "feat")
        self.assertEqual(gitwatch.pr_check(self.r.work, "nada", "feat"), "La rama nada no está en GitHub")


if __name__ == "__main__":
    unittest.main()
