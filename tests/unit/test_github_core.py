"""Core.github: crear el servicio de una cuenta no debe entrar en recursión aunque el redibujado lo vuelva a pedir."""
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica import core as core_mod  # noqa: E402
from isla_dinamica.services import github as github_mod  # noqa: E402


class FakeCore:
    """Lo mínimo que usa la property: al cambiar, la ventana vuelve a leer core.github (como pages/home.py)."""
    github = core_mod.Core.github

    def __init__(self, login="BitBro404"):
        self.gh_accounts = NS(current=login, env=lambda login=None: {})
        self._github = {}
        self.events = NS(github=lambda kind, p: None)
        self.git = NS(repos=[])
        self.redraws = 0

    def feature(self, name):
        return True

    def changed(self, kind=None):
        self.redraws += 1
        _ = self.github.review          # lo que hace la página de inicio al redibujar


class CoreGitHubTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(github_mod.GLib, "find_program_in_path", lambda name: None)   # sin gh: sin red
        p.start()
        self.addCleanup(p.stop)

    def test_creating_an_account_service_does_not_recurse(self):
        c = FakeCore()
        gh = c.github
        self.assertEqual(gh.login, "BitBro404")
        self.assertIs(c.github, gh)
        self.assertEqual(len(c._github), 1)
        self.assertGreaterEqual(c.redraws, 1)

    def test_each_account_keeps_its_own_service(self):
        c = FakeCore("WM-LuisP")
        a = c.github
        c.gh_accounts.current = "BitBro404"
        b = c.github
        self.assertIsNot(a, b)
        c.gh_accounts.current = "WM-LuisP"
        self.assertIs(c.github, a)


if __name__ == "__main__":
    unittest.main()
