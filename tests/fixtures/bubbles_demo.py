"""Tres actividades a la vez: recordatorio en 3 min (píldora), pomodoro y temporizador (burbujas).
DOCK=left para probar la isla en vertical. No toca ~/.config."""
import os
import time


def setup(core):
    core.config.save = lambda: None
    rm = core.reminders
    rm._save = rm.on_change
    rm.items = []
    rm.add("Daily con el equipo", time.time() + 180)
    core.pomo.start()
    core.start_timer(300)
    if os.environ.get("DOCK"):
        core.set_dock(os.environ["DOCK"], 0.5)
