"""Sección DEV: aviso de PR nuevas, punto de novedades de git/GitHub y monitor principal (sin GTK)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from isla_dinamica.services.devnews import DevNews  # noqa: E402
from isla_dinamica.services.github import inbox_item  # noqa: E402
from isla_dinamica.util.screens import primary_index  # noqa: E402
from test_github_alerts import bare_github, raw  # noqa: E402


def pr(i, url=None):
    return {"id": f"PR_{i}", "num": i, "repo": "o/r", "title": f"PR {i}", "author": "ana",
            "url": url or f"https://github.com/o/r/pull/{i}", "ci": None, "review": None, "updated": i}


def gh():
    g = bare_github()
    g.theirs, g._theirs, g._alerted = [], None, set()
    return g


class NewPullRequestTest(unittest.TestCase):
    def test_new_pr_from_others_alerts_after_the_first_load(self):
        g = gh()
        g.theirs = [pr(1)]
        g._notify_changes()
        self.assertEqual(g.events, [])                 # primera carga: las que ya había no avisan
        g.theirs = [pr(2), pr(1)]
        g._notify_changes()
        self.assertEqual([(k, p["num"]) for k, p in g.events], [("new_pr", 2)])

    def test_not_twice_if_the_inbox_already_announced_it(self):
        g = gh()
        g._notify_changes()
        g.inbox = [inbox_item(raw(9, path="pulls/9"))]
        g._seen = set()
        g._notify_inbox()                              # la bandeja avisó de o/r#9
        g.events.clear()
        g.theirs = [pr(9)]
        g._notify_changes()
        self.assertEqual(g.events, [])


class DevNewsTest(unittest.TestCase):
    def test_dot_until_seen(self):
        d = DevNews()
        self.assertFalse(d.pending)
        d.mark("behind", "/p/web")
        d.mark("pr", "PR_2")
        self.assertTrue(d.pending)
        self.assertEqual(d.count(), 2)
        d.seen("pr")                                   # abrió GitHub: quedan los commits por bajar
        self.assertEqual(d.count(), 1)
        d.seen()
        self.assertFalse(d.pending)

    def test_pulled_repos_clear_their_dot(self):
        d = DevNews()
        d.mark("behind", "/p/web")
        d.mark("behind", "/p/api")
        d.still_behind({"/p/api"})                     # /p/web ya hizo pull
        self.assertEqual(d.count(), 1)
        d.still_behind(set())
        self.assertFalse(d.pending)

    def test_changes_are_reported(self):
        calls = []
        d = DevNews(on_change=lambda: calls.append(1))
        d.mark("pr", "x")
        d.mark("pr", "x")                              # repetida: no cambia nada
        d.seen()
        d.seen()
        self.assertEqual(len(calls), 2)


class PrimaryMonitorTest(unittest.TestCase):
    def test_declared_primary_wins(self):
        self.assertEqual(primary_index([(1601, 0), (0, 0)], primary=0), 0)

    def test_without_primary_the_one_at_the_origin(self):
        # labwc no declara principal: el de arriba a la izquierda (el portátil en 0,0)
        self.assertEqual(primary_index([(1601, 0), (0, 0)]), 1)
        self.assertEqual(primary_index([(0, 300), (1920, 0)]), 0)

    def test_empty(self):
        self.assertIsNone(primary_index([]))


if __name__ == "__main__":
    unittest.main()
