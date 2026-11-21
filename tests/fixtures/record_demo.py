"""Graba la pantalla de la isla 5 s de verdad (en Vídeos/Grabaciones) y la detiene; el video se borra al salir."""
import atexit
import os

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    made = []

    core.recorder.audio = os.environ.get("REC_AUDIO", "none")

    def start():
        mon = next(iter(core.windows))
        core.record(mon)
        GLib.timeout_add(600, lambda: (made.append(core.recorder.path), False)[1])
        GLib.timeout_add(5500, lambda: (core.recorder.stop(), False)[1])
        return False
    GLib.timeout_add(1000, start)

    def cleanup():
        for p in made:
            print("video:", p, os.path.getsize(p) if p and os.path.exists(p) else "NO EXISTE")
            if p and os.path.exists(p):
                os.remove(p)
    atexit.register(cleanup)
