"""Simula un despliegue: empieza (t=2 s), sigue en curso y falla (t=13 s). No toca ~/.config."""
import time

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    dp = core.deploys
    dp.refresh = lambda: None          # sin consultas reales
    now = time.time()
    base = {"repo": "WMBLACKCODE/wmservice-backend", "name": "wmservice-backend", "project": "WMCoreDB",
            "url": "https://example.invalid", "by": "railway-app[bot]"}
    old = dict(base, id="D1", env="QA", state="SUCCESS", created=now - 7200, changed=now - 7000,
               commit="Merge pull request #16 from WMBLACKCODE/qa")
    run = dict(base, id="D2", env="production", state="IN_PROGRESS", created=now - 95, changed=now - 95,
               commit="Paso a producción 21-11-2026 (qa → main)")
    GLib.timeout_add(1000, lambda: dp.apply({"D1": old}) or False)
    GLib.timeout_add(2000, lambda: dp.apply({"D1": old, "D2": run}) or False)
    GLib.timeout_add(13000, lambda: dp.apply({"D1": old, "D2": dict(run, state="FAILURE", changed=time.time())}) or False)
