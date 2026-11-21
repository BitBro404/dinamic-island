"""Levanta un servidor de prueba en :5173 (carpeta temporal «demo-frontend») y lo detiene desde la isla."""
import os
import subprocess
import tempfile

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    folder = os.path.join(tempfile.mkdtemp(prefix="isla-"), "demo-frontend")
    os.makedirs(folder)
    procs = []
    GLib.timeout_add(1000, lambda: procs.append(subprocess.Popen(
        ["python3", "-m", "http.server", "5173", "--bind", "127.0.0.1"], cwd=folder,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)) or False)

    def stop_from_island():
        w = next(iter(core.windows.values()))
        w._sv_stop(5173)          # primer clic: pide confirmación
        w._sv_stop(5173)          # segundo clic: detiene
        return False
    GLib.timeout_add(12500, stop_from_island)
    GLib.timeout_add(30000, lambda: [p.kill() for p in procs] and False)   # por si acaso
