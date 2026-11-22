"""Varias actividades a la vez para el arnés (B7): pomodoro (píldora) + Bluetooth + temporizador + descarga.

Fuera de la píldora quedan 3 → 2 burbujas + «+1». Uso:
    python3 tests/harness.py pill bubble3 tasks --setup tests/fixtures/tasks_demo.py --out /tmp/opencode/isla-b7
Imprime una vez por combinación las burbujas calculadas (tooltip) y las filas de «Tareas en curso».
"""
import os
import runpy
import time

from isla_dinamica.ui.bubbles import bubble_tip

_bt_setup = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bluetooth_demo.py"))["setup"]


def setup(core):
    _bt_setup(core)                                  # Bluetooth falso «Auriculares · 82%»
    feats = core.config.data["features"]
    feats["bub_more"] = feats["downloads"] = True
    core.pomo.start()
    core.start_timer(10 * 60)
    fake = {"/tmp/x.zip.crdownload": {"name": "informe.zip", "size": 1, "speed": 0.0, "t": time.time(),
                                      "started": time.time()}}
    core.downloads.scan = lambda: None               # la carpeta real no sobrescribe la descarga falsa
    core.downloads.active = fake

    original, seen = core.refresh, set()

    def debug_refresh():
        original()
        windows = list(core.windows.values())
        if windows:
            w = windows[0]
            tips = tuple(bubble_tip(a) for a in w.bubbles)
            if tips and tips not in seen:
                seen.add(tips)
                print("TASKS_BUBBLES:", tips, flush=True)
        return False
    core.refresh = debug_refresh
