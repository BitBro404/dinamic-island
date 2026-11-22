"""Subpáginas de GitHub: el primer repo vigilado de la cuenta y una PR abierta simulada (no toca GitHub).

    python3 tests/harness.py github ghacct ghrepo ghpr --wait 5 --setup tests/fixtures/github_pages_demo.py
"""
from gi.repository import GLib

PR = {"id": "x", "num": 42, "title": "feat: exportar evidencias a PDF", "url": "https://github.com/notifications",
      "repo": "WMBLACKCODE/wmservice-frontend", "author": "mmaciasgg", "draft": False, "updated": 0,
      "merged": None, "review": "REVIEW_REQUIRED", "ci": "SUCCESS"}
DETAIL = {"state": "OPEN", "ci": "SUCCESS", "mergeable": "MERGEABLE", "headRefName": "feat/pdf",
          "baseRefName": "devel", "additions": 214, "deletions": 18, "changedFiles": 6,
          "body": "Agrega el botón Exportar en la vista de tareas y genera el PDF con las evidencias adjuntas.",
          "commits": [{"messageHeadline": "feat: botón exportar", "authors": [{"login": "mmaciasgg"}],
                       "committedDate": "2026-11-22T13:00:00Z", "oid": "a1b2c3d4"}]}


def setup(core):
    def gh_pages():
        for w in core.windows.values():
            for obj in w.page_objs:
                if hasattr(obj, "sel_repo"):
                    yield obj

    core.github.pr_detail = lambda p, cb: cb(dict(DETAIL), "")

    def pick():
        repos = [s for s in core.git.repos if s.get("slug") and core.github.access.get(s["slug"])]
        for obj in gh_pages():
            obj.sel_pr = PR
            if repos:
                s = repos[0]
                obj.sel_repo = s["path"]
                if not (s["ahead"] or s["behind"]):     # commits simulados para ver la lista
                    s.update(behind=2, ahead=1, incoming=[
                        {"sha": "9f3c2a1", "author": "bmoralw", "ts": 1795370000, "subject":
                         "fix(dashboard): utilidad real basada en lo facturado",
                         "body": "Usa el total facturado en vez del cotizado.\n\nCo-Authored-By: x"},
                        {"sha": "41be7d0", "author": "mmaciasgg", "ts": 1795360000,
                         "subject": "feat: filtro por cliente en tareas", "body": ""}],
                        outgoing=[{"sha": "c0ffee1", "author": "WM-LuisP", "ts": 1795375000,
                                   "subject": "chore: limpiar logs de depuración", "body": ""}])
        return not repos

    GLib.timeout_add(1000, pick)
