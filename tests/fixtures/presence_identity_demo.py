"""Identidad en «Presencia» sin cámara real: rostro registrado y pregunta «¿eras tú?».

    python3 tests/harness.py presence --setup tests/fixtures/presence_identity_demo.py

La foto es sintética y vive solo en memoria; no se escribe en disco.
"""
import os
import tempfile
import time

import numpy as np

from isla_dinamica.services.identity import Gallery


def setup(core):
    core.config.save = lambda: None
    core.config.data["features"]["presence"] = True
    p = core.presence
    p._tick = lambda: None                       # el hilo real no toca el estado
    p.state = os.environ.get("PRESENCE_STATE", "confirm")
    p.seconds_left = lambda: None
    p.last_seen = time.time() - 40
    p.test_result = "Modelos listos · galería local"
    p.gallery = Gallery(os.path.join(tempfile.mkdtemp(), "gallery.json"))  # nunca la galería real
    p.gallery.add([0.1] * 128)
    p.gallery.add([0.2] * 128)
    p.enrolling = False

    frame = np.full((240, 320, 3), 70, np.uint8)  # fondo gris: imagen de prueba, nunca una captura real
    frame[50:190, 100:220] = (150, 170, 190)
    frame[95:110, 130:150] = (30, 30, 30)
    frame[95:110, 175:195] = (30, 30, 30)
    frame[145:160, 140:185] = (60, 60, 60)
    p.pending_prompt = {"frame": frame, "feature": [0.1] * 128,
                        "expires": time.time() + 20, "source": "doubt"}
