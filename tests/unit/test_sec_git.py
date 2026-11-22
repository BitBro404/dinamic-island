"""S10: la isla ejecuta git sola en las carpetas vigiladas; un .git/config no confiable no debe ejecutar nada."""
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitrepo import Repos, commit, git  # noqa: E402
from isla_dinamica.services import gitwatch  # noqa: E402


class Trap:
    """Script que deja una marca si alguien lo ejecuta."""
    def __init__(self, folder, name):
        self.mark = os.path.join(folder, name + ".ran")
        self.path = os.path.join(folder, name + ".sh")
        with open(self.path, "w") as f:
            f.write(f"#!/bin/sh\ntouch '{self.mark}'\nexit 0\n")
        os.chmod(self.path, os.stat(self.path).st_mode | stat.S_IEXEC)

    @property
    def ran(self):
        return os.path.exists(self.mark)


class UntrustedRepoTest(unittest.TestCase):
    def setUp(self):
        self.r = Repos()
        self.addCleanup(self.r.cleanup)
        self.traps = tempfile.TemporaryDirectory()
        self.addCleanup(self.traps.cleanup)

    def trap(self, name):
        return Trap(self.traps.name, name)

    def test_fsmonitor_is_not_run_by_the_status_scan(self):
        t = self.trap("fsmonitor")
        git(self.r.work, "config", "core.fsmonitor", t.path)
        gitwatch.repo_status(self.r.work)
        self.assertFalse(t.ran)

    def test_hooks_do_not_run_in_automatic_commands(self):
        t = self.trap("hook")
        hook = os.path.join(self.r.work, ".git", "hooks", "reference-transaction")
        os.symlink(t.path, hook)
        gitwatch._git(self.r.work, "update-ref", "refs/heads/copia", "HEAD")
        self.assertFalse(t.ran)

    def test_hooks_still_run_in_what_the_user_asks(self):
        t = self.trap("post-merge")
        os.symlink(t.path, os.path.join(self.r.work, ".git", "hooks", "post-merge"))
        git(self.r.work, "switch", "-q", "-c", "tema")
        commit(self.r.work, "b.txt")
        git(self.r.work, "switch", "-q", "main")
        ok, msg = gitwatch.run_op(self.r.work, "merge", None, branch="tema")
        self.assertTrue(ok, msg)
        self.assertTrue(t.ran)                         # husky y compañía siguen funcionando al hacer merge

    def test_automatic_fetch_skips_local_remotes_with_uploadpack(self):
        t = self.trap("uploadpack")
        git(self.r.work, "config", "remote.origin.uploadpack", t.path)
        w = gitwatch.GitWatch.__new__(gitwatch.GitWatch)
        with mock.patch.object(gitwatch.GLib, "idle_add"):
            w._scan([os.path.dirname(self.r.work)], True)
        self.assertFalse(t.ran)


class RemoteKindTest(unittest.TestCase):
    def test_network_remotes(self):
        for url in ("https://github.com/o/r.git", "ssh://git@github.com/o/r.git", "git@github.com:o/r.git",
                    "http://localhost:3000/o/r.git"):
            self.assertTrue(gitwatch.network_remote(url), url)
        for url in ("/srv/git/r.git", "../r.git", "file:///srv/r.git", "ext::sh -c evil", "", None,
                    "C:/r.git", "-uevil:x"):
            self.assertFalse(gitwatch.network_remote(url), url)

    def test_token_stays_scoped_to_github(self):
        env = gitwatch.auth_env("tok")
        pairs = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(int(env["GIT_CONFIG_COUNT"]))}
        self.assertIn("credential.https://github.com.helper", pairs)
        self.assertNotIn("credential.helper", pairs)
        self.assertEqual(pairs.get("core.fsmonitor"), "false")
        self.assertEqual(env["ISLA_GH_TOKEN"], "tok")


if __name__ == "__main__":
    unittest.main()
