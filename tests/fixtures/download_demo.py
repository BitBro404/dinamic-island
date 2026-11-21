"""Simula una descarga de Chrome en la carpeta Descargas (se borra al terminar la prueba)."""
import atexit
import os

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    d = core.downloads.dir
    part, final = os.path.join(d, "isla-prueba.bin.crdownload"), os.path.join(d, "isla-prueba.bin")
    state = {"n": 0}

    def grow():
        with open(part, "ab") as f:
            f.write(os.urandom(256 * 1024))      # ~256 KB cada 0,2 s ≈ 1,3 MB/s
        state["n"] += 1
        if state["n"] >= 45:
            os.rename(part, final)
            return False
        return True
    GLib.timeout_add(2000, lambda: GLib.timeout_add(200, grow) and False)
    atexit.register(lambda: [os.remove(p) for p in (part, final) if os.path.exists(p)])
