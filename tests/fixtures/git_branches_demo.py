"""Página de un repo con ramas, PR y stash sobre un repo temporal (no toca tus repos ni GitHub).

    python3 tests/harness.py ghrepo ghrepo --wait 6 --setup tests/fixtures/git_branches_demo.py
Vigila SOLO el repo temporal mientras dura la prueba (no se guarda en config.json). Pasos:
  1.ª captura: ramas, selector de PR y stash.  2.ª captura: aviso al pedir PR de una rama sin subir
  y el desplegable de ramas abierto (captura completa en $DEMO_OUT/popup.png).
Con DEMO_CONFLICT=1 deja un merge a medias con un conflicto en a.txt (panel «MERGE EN CURSO»).
"""
import os
import subprocess
import sys

from gi.repository import GLib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit"))
from gitrepo import Repos, commit, git  # noqa: E402

SLUG = "BitBro404/isla-demo"


def make_repo():
    r = Repos()
    w = r.work
    git(w, "switch", "-q", "-c", "devel")
    commit(w, "d.txt", msg="devel")
    git(w, "push", "-q", "-u", "origin", "devel")
    git(w, "switch", "-q", "-c", "feat/exportar-pdf")
    commit(w, "f.txt", msg="feat: exportar a PDF")           # sin subir
    git(w, "switch", "-q", "main")
    if os.environ.get("DEMO_CONFLICT"):        # merge a medias con conflicto en a.txt
        git(w, "switch", "-q", "-c", "feat/colores")
        commit(w, "a.txt", "azul", msg="colores: azul")
        git(w, "switch", "-q", "main")
        commit(w, "a.txt", "rojo", msg="main: rojo")
        try:
            git(w, "merge", "--no-edit", "feat/colores")
        except RuntimeError:
            pass
    # URL de GitHub (el repo no existe: el fetch de fondo falla sin más) para que la isla lo trate como de la cuenta
    git(w, "remote", "set-url", "origin", f"https://github.com/{SLUG}.git")
    for i, msg in enumerate(() if os.environ.get("DEMO_CONFLICT") else
                            ("prueba de colores", "arreglo a medias del login")):
        with open(os.path.join(w, "a.txt"), "w") as f:
            f.write(f"cambio {i}")
        git(w, "stash", "push", "-q", "-m", msg)
    return r


def setup(core):
    r = make_repo()
    core._demo_repo = r                                     # que no se borre mientras corre
    gw = core.git
    gw.__class__ = type("DemoGitWatch", (type(gw),), {"folders": property(lambda self: [r.tmp.name])})
    core.github.access[SLUG] = {"push": True}
    gw.refresh()

    def page():
        return [o for w in core.windows.values() for o in w.page_objs if type(o).__name__ == "GitHubPage"][0]

    def tag():
        for s in gw.repos:
            if s["path"] == r.work:
                page().sel_repo = r.work
                return False
        return True

    def pr_unpushed():
        p = page()
        p.rp_from.set_active_id("feat/exportar-pdf")
        p._do_pr()
        GLib.timeout_add(600, popup)
        return False

    def popup():
        page().rp_branch.popup()
        out = os.environ.get("DEMO_OUT")
        if out:
            GLib.timeout_add(900, lambda: subprocess.run(["grim", os.path.join(out, "popup.png")]) and False)
        return False

    GLib.timeout_add(300, tag)
    if not os.environ.get("DEMO_CONFLICT"):
        GLib.timeout_add(13000, pr_unpushed)
