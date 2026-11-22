"""Proyectos de la cuenta: añade dos repos temporales a la cuenta elegida SIN guardar config.json.

    python3 tests/harness.py ghproj github --wait 6 --setup tests/fixtures/account_projects_demo.py
"""
import os
import sys

from gi.repository import GLib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit"))
from gitrepo import Repos, commit  # noqa: E402


def setup(core):
    core.config.save = lambda: None                 # la prueba no toca tu config.json
    a, b = Repos(), Repos()
    commit(a.work, "nuevo.txt", msg="sin subir")    # ↑1 para que se vea en «Commits por sincronizar»
    core._demo_repos = (a, b)

    def add():
        print("añadir:", core.git.add_account_folder(a.work), core.git.add_account_folder(b.tmp.name),
              "repetido:", core.git.add_account_folder(a.work), flush=True)
        return False
    GLib.timeout_add(500, add)
