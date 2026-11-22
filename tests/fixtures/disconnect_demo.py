"""Desconectar un repo: dos repos temporales vigilados (sin tocar config.json). A los 6 s pide confirmación para
desconectar «web» (se ve «¿Seguro?»); con DISCONNECT_DONE=1 confirma y aparece en DESCONECTADOS.

    python3 tests/harness.py projects --start 5 --wait 4 --setup tests/fixtures/disconnect_demo.py
"""
import os
import shutil
import sys
import tempfile

from gi.repository import GLib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit"))
from gitrepo import Repos, commit  # noqa: E402


def setup(core):
    core.config.save = lambda: None
    base = tempfile.mkdtemp(prefix="isla-pj-")
    repos = []
    for name in ("web", "api"):
        r = Repos()
        dst = os.path.join(base, name)
        shutil.move(r.work, dst)
        r.work = dst
        repos.append(r)
    commit(repos[1].work, "nuevo.txt", msg="sin subir")
    core._demo_repos = repos
    core.config.data["git_folders"] = [base]
    core.config.data["git_ignored"] = []
    core.git.refresh()
    done = os.environ.get("DISCONNECT_DONE") == "1"

    def click():
        w = next(iter(core.windows.values()))
        pg = next(o for o in w.page_objs if type(o).__name__ == "ProjectsPage")
        key = f"repo:{repos[0].work}"
        pg._pj_confirm(key, lambda: pg._pj_disconnect(repos[0].work), "¿Desconectar web? La isla dejará de "
                       "vigilarlo. Pulsa «¿Seguro?»")
        if done:
            pg._pj_confirm(key, lambda: pg._pj_disconnect(repos[0].work), "")
        return False
    GLib.timeout_add(6000, click)
