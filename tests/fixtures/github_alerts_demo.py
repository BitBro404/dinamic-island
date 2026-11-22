"""Demo de alertas de GitHub/git: una PR nueva, commits sin subir y la lista de notificaciones.

    python3 tests/harness.py pill pill notifs --setup tests/fixtures/github_alerts_demo.py
"""
from gi.repository import GLib


def setup(core):
    pr = {"kind": "PR", "title": "feat: subir y gestionar logos de empresas", "repo": "WMBLACKCODE/wmcore-backend",
          "reason": "repo que sigues", "url": "https://github.com/notifications"}
    git = {"name": "wmservice-backend", "ahead": 2, "branch": "main", "upstream": "origin/main", "path": "/tmp"}
    GLib.timeout_add(5000, lambda: core.events.github("inbox", pr) and False)
    GLib.timeout_add(8000, lambda: core.events.git("ahead", git) and False)
