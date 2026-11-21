#!/usr/bin/env python3
"""Arnés de pruebas: abre páginas de la isla y les saca una captura.

    python3 tests/harness.py home weather github more
    python3 tests/harness.py github --setup tests/fixtures/github_fake.py --out /tmp/capturas

- Detiene la isla que esté corriendo y arranca la versión de este proyecto.
- Ignora el ratón real (no se abre ni se cierra sola mientras se prueba).
- La página especial «pill» captura la isla cerrada (la píldora).
- Por cada página: la abre, espera y guarda <out>/<página>.png (sólo la zona de la isla, monitor principal).
- --setup archivo.py: debe definir setup(core) para inyectar datos falsos antes de abrir las páginas.
- Al terminar vuelve a arrancar la isla instalada (~/.local/bin/isla-dinamica).
"""
import argparse
import os
import runpy
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
INSTALLED = os.path.expanduser("~/.local/bin/isla-dinamica")


def stop_running():
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    me = os.getpid()
    for line in out.splitlines()[1:]:
        pid, _, args = line.strip().partition(" ")
        parts = args.split()
        if int(pid) != me and len(parts) >= 2 and parts[0].endswith("python3") and \
                (parts[1].endswith("isla-dinamica") or parts[1].endswith("isla.py")):
            subprocess.run(["kill", pid])
    time.sleep(0.8)


def restart_installed():
    if os.path.exists(INSTALLED):
        env = dict(os.environ, ISLA_NO_WELCOME="1")
        subprocess.Popen([INSTALLED], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "capturas"))
    ap.add_argument("--wait", type=float, default=2.5, help="segundos por página")
    ap.add_argument("--start", type=float, default=4.0, help="segundos antes de la primera página")
    ap.add_argument("--setup", help="archivo .py con setup(core)")
    ap.add_argument("--no-restart", action="store_true", help="no volver a arrancar la isla instalada")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.environ.setdefault("ISLA_NO_WELCOME", "1")

    from gi.repository import GLib
    from isla_dinamica import core as core_mod, main as main_mod, window

    window.IslandWindow._on_enter = lambda *_: False     # ignorar el ratón real
    window.IslandWindow._on_leave = lambda *_: False
    setup = runpy.run_path(a.setup)["setup"] if a.setup else None
    results = []

    orig_init = core_mod.Core.__init__

    def init(self, app):
        orig_init(self, app)
        if setup:
            setup(self)
        w = next(iter(self.windows.values()))
        queue = list(a.pages)

        def shoot(name):
            g = w.monitor.get_geometry()
            x, y = w._last_xy
            ww, hh = w.get_allocated_width(), w.get_allocated_height()
            n = sum(1 for r in results if r[0] == name)
            path = os.path.join(a.out, f"{name}.png" if not n else f"{name}-{n + 1}.png")
            # margen horizontal amplio: los paneles del escritorio desplazan un poco el origen
            geo = f"{g.x + x - 90},{g.y + y - 8} {ww + 180}x{hh + 16}"
            ok = subprocess.run(["grim", "-g", geo, path]).returncode == 0
            results.append((name, path if ok else "ERROR al capturar"))

        def step():
            if not queue:
                app.quit()
                return False
            name = queue.pop(0)
            for win in self.windows.values():
                if name == "pill":          # la isla cerrada (píldora compacta)
                    win.hover = False
                    win.page = "home"
                    win.refresh()
                else:
                    win.hover = True
                    win.go(name)
            GLib.timeout_add(int(a.wait * 1000), lambda: (shoot(name), step()) and False)
            return False

        GLib.timeout_add(int(a.start * 1000), step)

    core_mod.Core.__init__ = init
    stop_running()
    try:
        main_mod.main()
    finally:
        if not a.no_restart:
            restart_installed()
    for name, path in results:
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
