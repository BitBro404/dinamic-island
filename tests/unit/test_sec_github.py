"""S11: lo que sale de .git/config o de gh no puede inyectar nada en las consultas GraphQL a GitHub."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services.github import GitHub  # noqa: E402
from isla_dinamica.services.gitwatch import github_slug  # noqa: E402


class SlugTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(github_slug("git@github.com:BitBro404/dinamic-island.git"), "BitBro404/dinamic-island")
        self.assertEqual(github_slug("https://github.com/o-1/r.repo_x"), "o-1/r.repo_x")

    def test_quotes_and_braces_are_not_a_slug(self):
        for url in ('https://github.com/o") { viewer { login } } x: repository(owner: "a/r',
                    'https://github.com/o/r"}', "https://github.com/o/r{x}", "https://github.com/o b/r",
                    "https://github.com/-o/r", "https://github.com/o/.."):
            self.assertIsNone(github_slug(url), url)


class QueryTest(unittest.TestCase):
    def gh(self, login, repos=()):
        g = GitHub.__new__(GitHub)
        g.ran = []
        g._run = lambda argv, cb: g.ran.append(argv)
        g.login, g.state, g.error, g.loading = login, "ok", None, True
        g.on_change = lambda: None
        g.my_repos = lambda: list(repos)
        return g

    def test_bad_login_is_not_queried(self):
        g = self.gh('ana" is:pr author:otro')
        g._query_prs()
        self.assertEqual(g.ran, [])
        self.assertEqual(g.state, "error")

    def test_good_login_is_queried(self):
        g = self.gh("BitBro404", ["BitBro404/isla"])
        g._query_prs()
        self.assertEqual(len(g.ran), 1)
        self.assertIn("author:BitBro404", g.ran[0][-1])


if __name__ == "__main__":
    unittest.main()
