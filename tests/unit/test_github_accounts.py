"""Cuentas de gh, commits por subir/bajar y acciones de PR (sin red: gh y git falsos)."""
import os
import sys
import unittest
from unittest import mock
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from isla_dinamica.services import ghaccounts, gitwatch  # noqa: E402
from isla_dinamica.services.github import GitHub, ci_state, merge_flag  # noqa: E402

STATUS = """github.com
  ✓ Logged in to github.com account WM-LuisP (keyring)
  - Active account: true
  - Token scopes: 'repo'

  ✓ Logged in to github.com account BitBro404 (keyring)
  - Active account: false
"""


def fake_token(login):
    return "gh" + "o_" + login.lower().ljust(36, "x")      # se arma en tiempo de ejecución


class FakeConfig:
    def __init__(self, data=None):
        self.data, self.saved = dict(data or {}), 0

    def save(self):
        self.saved += 1


def accounts(saved=None, auth_ok=True):
    calls = []

    def sh(argv, timeout=8):
        calls.append(argv)
        if argv[:3] == ["gh", "auth", "status"]:
            return True, "", STATUS
        if argv[:3] == ["gh", "auth", "token"]:
            return True, fake_token(argv[-1]) + "\n", ""
        return False, "", ""

    def runner(argv, cb, **kw):
        calls.append(argv)
        cb(auth_ok, "", "" if auth_ok else "Error executing command as another user: Not authorized")

    a = ghaccounts.Accounts(FakeConfig({"github_account": saved} if saved else {}), lambda: None, sh=sh, runner=runner)
    return a, calls


class AccountsTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(ghaccounts.GLib, "find_program_in_path", lambda name: "/usr/bin/" + name)
        p.start()
        self.addCleanup(p.stop)

    def test_parse_status_lists_all_and_active(self):
        self.assertEqual(ghaccounts.parse_status(STATUS), (["WM-LuisP", "BitBro404"], "WM-LuisP"))

    def test_current_defaults_to_gh_active_then_saved(self):
        self.assertEqual(accounts()[0].current, "WM-LuisP")
        self.assertEqual(accounts("BitBro404")[0].current, "BitBro404")
        self.assertEqual(accounts("Gone")[0].current, "WM-LuisP")      # sesión cerrada: vuelve a la activa

    def test_env_carries_that_accounts_token(self):
        a, _ = accounts()
        self.assertEqual(a.env("BitBro404"), {"GH_TOKEN": fake_token("BitBro404")})

    def test_switch_asks_password_and_saves(self):
        a, calls = accounts()
        res = []
        a.switch("BitBro404", lambda ok, msg: res.append(ok))
        self.assertIn(["pkexec", "/bin/true"], calls)
        self.assertEqual((res, a.current, a.config.saved), ([True], "BitBro404", 1))

    def test_switch_denied_keeps_account(self):
        a, _ = accounts(auth_ok=False)
        res = []
        a.switch("BitBro404", lambda ok, msg: res.append(ok))
        self.assertEqual((res, a.current), ([False], "WM-LuisP"))
        self.assertIn("sigues con @WM-LuisP", a.error)

    def test_switch_never_stays_waiting_even_if_the_follow_up_fails(self):
        a, _ = accounts()
        changes = []
        a.on_change = lambda: changes.append(a.switching)

        def boom(ok, msg):
            raise RuntimeError("fallo al refrescar")
        with self.assertRaises(RuntimeError):
            a.switch("BitBro404", boom)
        self.assertIsNone(a.switching)
        self.assertEqual(changes[-1], None)          # la página se redibuja sin «Esperando…»
        self.assertEqual(a.current, "BitBro404")

    def test_switch_to_unknown_or_same_does_nothing(self):
        a, calls = accounts()
        a.switch("WM-LuisP")
        a.switch("Nadie")
        self.assertNotIn(["pkexec", "/bin/true"], calls)


class GitTest(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(gitwatch.github_slug("git@github.com:o/r.git"), "o/r")
        self.assertEqual(gitwatch.github_slug("https://github.com/o/r"), "o/r")
        self.assertIsNone(gitwatch.github_slug("https://gitlab.com/o/r.git"))

    def test_parse_log(self):
        out = "abc1234\x1fAna\x1f1700000000\x1ffix: algo\x1fcuerpo\nlargo\x1e\ndef5678\x1fLuis\x1f1700000100\x1ffeat\x1f\x1e\n"
        c = gitwatch.parse_log(out)
        self.assertEqual([(x["sha"], x["author"], x["ts"], x["subject"]) for x in c],
                         [("abc1234", "Ana", 1700000000, "fix: algo"), ("def5678", "Luis", 1700000100, "feat")])
        self.assertEqual(c[0]["body"], "cuerpo\nlargo")

    def test_token_goes_in_env_not_in_config_values(self):
        tok = fake_token("x")
        env = gitwatch.auth_env(tok)
        self.assertEqual(env["ISLA_GH_TOKEN"], tok)
        self.assertNotIn(tok, env["GIT_CONFIG_VALUE_1"])
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], "")          # anula los demás helpers
        self.assertNotIn("ISLA_GH_TOKEN", gitwatch.auth_env(None))


def bare_github(access=None):
    g = GitHub.__new__(GitHub)
    g.ran, g.refreshed = [], 0
    g._run = lambda argv, cb: (g.ran.append(argv), cb(True, "{}", ""))
    g.refresh = lambda: setattr(g, "refreshed", g.refreshed + 1)
    g.access, g.repo_info = access or {}, {}
    g.repos = lambda: [{"slug": "o/a"}, {"slug": "o/b"}, {"slug": None}]
    return g


class PrTest(unittest.TestCase):
    def test_merge_flag_follows_repo_settings(self):
        self.assertEqual(merge_flag(None), "--merge")
        self.assertEqual(merge_flag({"mergeCommitAllowed": False, "squashMergeAllowed": True}), "--squash")
        self.assertEqual(merge_flag({"mergeCommitAllowed": False, "squashMergeAllowed": False,
                                     "rebaseMergeAllowed": True}), "--rebase")

    def test_ci_state(self):
        self.assertIsNone(ci_state([]))
        self.assertEqual(ci_state([{"conclusion": "SUCCESS"}, {"state": "FAILURE"}]), "FAILURE")
        self.assertEqual(ci_state([{"conclusion": "SUCCESS"}, {"status": "IN_PROGRESS", "conclusion": ""}]), "PENDING")
        self.assertEqual(ci_state([{"conclusion": "SUCCESS"}, {"state": "SUCCESS"}]), "SUCCESS")

    def test_actions_build_the_right_gh_commands(self):
        g = bare_github()
        p = {"num": 7, "repo": "o/a"}
        res = []
        for action, body in (("approve", ""), ("changes", "arregla X"), ("merge", ""), ("close", "")):
            g.pr_action(p, action, body, lambda ok, msg: res.append(msg))
        self.assertEqual(g.ran, [["gh", "pr", "review", "7", "-R", "o/a", "--approve"],
                                 ["gh", "pr", "review", "7", "-R", "o/a", "--request-changes", "-b", "arregla X"],
                                 ["gh", "pr", "merge", "7", "-R", "o/a", "--merge"],
                                 ["gh", "pr", "close", "7", "-R", "o/a"]])
        self.assertEqual(res, ["Aprobada", "Cambios pedidos", "Fusionada", "Cerrada"])
        self.assertEqual(g.refreshed, 4)

    def test_my_repos_only_those_with_access(self):
        g = bare_github({"o/a": {"push": True}, "o/b": None})
        self.assertEqual(g.my_repos(), ["o/a"])


class AheadSyncTest(unittest.TestCase):
    def test_sync_uses_account_token_and_refreshes(self):
        w = gitwatch.GitWatch.__new__(gitwatch.GitWatch)
        w.syncing, w.on_change = {}, lambda: None
        w.token_for = lambda s: fake_token("a")
        w.refresh = lambda fetch=False: None
        seen = []
        orig_run, orig_thread, orig_idle = gitwatch._git_run, gitwatch.threading.Thread, gitwatch.GLib.idle_add
        gitwatch._git_run = lambda path, *a, timeout=10, token=None: (seen.append((a, token)) or
                                                                     NS(returncode=0, stdout="", stderr="ok"))
        gitwatch.threading.Thread = lambda target, daemon: NS(start=target)
        gitwatch.GLib.idle_add = lambda fn, *a: fn(*a)
        try:
            res = []
            w.sync({"path": "/r"}, "pull", lambda ok, msg: res.append(ok))
        finally:
            gitwatch._git_run, gitwatch.threading.Thread, gitwatch.GLib.idle_add = orig_run, orig_thread, orig_idle
        self.assertEqual(seen, [(("pull", "--ff-only"), fake_token("a"))])
        self.assertEqual((res, w.syncing), ([True], {}))


if __name__ == "__main__":
    unittest.main()
