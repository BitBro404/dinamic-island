"""Servidor de prueba en :5173 (carpeta temporal «demo-frontend»): la isla lo reinicia (↻) a los 9 s y muestra
otro recordado como detenido («demo-api», :8765). No guarda nada en la configuración del usuario."""
import os
import subprocess
import sys
import tempfile
import time

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    base = tempfile.mkdtemp(prefix="isla-")
    folder, api = os.path.join(base, "demo-frontend"), os.path.join(base, "demo-api")
    os.makedirs(folder)
    os.makedirs(api)
    core.config.data["servers_recent"] = [{
        "name": "demo-api", "port": 8765, "kind": "Servidor estático", "cwd": api, "when": time.time() - 3600,
        "argv": [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"], "path": os.environ["PATH"]}]
    procs = []
    GLib.timeout_add(1000, lambda: procs.append(subprocess.Popen(
        ["python3", "-m", "http.server", "5173", "--bind", "127.0.0.1"], cwd=folder,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)) or False)

    def restart_from_island():
        w = next(iter(core.windows.values()))
        pg = next(o for o in w.page_objs if type(o).__name__ == "ServersPage")
        pg._sv_restart(5173)          # primer clic: pide confirmación
        pg._sv_restart(5173)          # segundo clic: reinicia
        return False
    GLib.timeout_add(9000, restart_from_island)

    def cleanup():
        for p in procs:
            p.kill()
        subprocess.run(["pkill", "-f", "http.server 5173 --bind 127.0.0.1"])
        subprocess.run(["pkill", "-f", "http.server 8765 --bind 127.0.0.1"])
        return False
    GLib.timeout_add(40000, cleanup)
