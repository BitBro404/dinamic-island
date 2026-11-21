"""Recordatorios de prueba en memoria (no toca ~/.config): uno vence a los 8 s, otro en 4 min y dos más."""
import time


def setup(core):
    core.config.save = lambda: None
    rm = core.reminders
    rm._save = rm.on_change
    rm.items = []
    now = time.time()
    rm.add("Revisar el PR de facturación", now + 8)
    rm.add("Daily con el equipo", now + 240)
    rm.add("pagar la luz mañana a las 8")
    rm.add("tomar agua en 2 h")
