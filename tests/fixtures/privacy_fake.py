"""Simula que Chrome usa la cámara y Teams el micrófono (sin abrir dispositivos reales)."""
from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    pv = core.privacy
    pv.enabled = lambda: False          # el hilo real informa «nada»; ignoramos sus actualizaciones
    real_update = pv._update
    pv._update = lambda cam, mic: False
    GLib.timeout_add(1500, lambda: real_update(["Chrome"], ["Teams"]) or False)
