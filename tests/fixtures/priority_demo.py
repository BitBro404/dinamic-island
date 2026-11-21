"""Pomodoro + (tu música real si suena) y, con CARD=1, una notificación de Teams a los 2 s.
H12=1 pone la hora en 12 h; CALL=1 simula una llamada. No toca ~/.config."""
import os

from gi.repository import GLib


def setup(core):
    core.config.save = lambda: None
    if os.environ.get("H12"):
        core.set_feature("clock24", False)
    core.pomo.start()
    if os.environ.get("CALL"):
        au = core.audio
        orig = au._apply
        au._apply = lambda outs, mic, call: orig(outs, ["Teams"], "Google Chrome")
    if os.environ.get("CARD"):
        GLib.timeout_add(2000, lambda: core.show_event(
            12.0, kind="card", icon="mail-unread-symbolic", app="Microsoft Teams",
            title="Ana Gómez", body="¿Revisamos el PR de facturación antes de la daily?") and False)
