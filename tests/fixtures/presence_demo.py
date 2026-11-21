"""Sensor de presencia con estado falso (sin cámara): PRESENCE_STATE=warning|watching|present|off_hours|paused|no_cv."""
import os
import time


def setup(core):
    core.config.save = lambda: None
    core.config.data["features"]["presence"] = True
    p = core.presence
    p._tick = lambda: None              # el hilo real no toca el estado
    p.state = os.environ.get("PRESENCE_STATE", "warning")
    p.seconds_left = lambda: 22 if p.state == "warning" else 140
    p.last_seen = time.time() - 130
    if p.state == "no_cv":
        p.error = "Instala OpenCV: sudo apt install python3-opencv opencv-data"
    if p.state == "paused":
        p.conf["paused_until"] = time.time() + 3600
    p.test_result = "Te veo"
