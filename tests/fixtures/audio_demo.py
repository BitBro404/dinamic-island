"""Reproduce de verdad un ritmo (bombo + platillo + melodía) con pacat para probar las barras y el brillo.
CALL=1 simula además una llamada (Teams con micrófono). No toca ~/.config."""
import atexit
import math
import os
import struct
import subprocess
import tempfile
import wave


def _beat(path, secs=40, rate=22050):
    frames = bytearray()
    notes = (220, 277, 330, 440)
    for i in range(rate * secs):
        t = i / rate
        beat = t % 0.5
        kick = math.sin(2 * math.pi * 60 * beat) * math.exp(-beat * 18) * 0.9
        hat = (((i * 1103515245 + 12345) >> 16) % 2000 / 1000 - 1) * math.exp(-((t + 0.25) % 0.5) * 60) * 0.25
        mel = math.sin(2 * math.pi * notes[int(t * 2) % 4] * t) * 0.25 * (0.5 + 0.5 * math.sin(t * 3))
        frames += struct.pack("<h", int(max(-1, min(1, kick + hat + mel)) * 14000))
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def setup(core):
    core.config.save = lambda: None
    path = os.path.join(tempfile.gettempdir(), "isla-beat.wav")
    if not os.path.exists(path):
        _beat(path)
    p = subprocess.Popen(["pacat", "--playback", "--file-format=wav", "--client-name=Reproductor",
                          "--stream-name=Prueba", path])
    atexit.register(p.terminate)
    if os.environ.get("CALL"):
        au = core.audio
        orig = au._apply

        def fake(outs, mic, call):
            return orig(outs, ["Teams"], "Teams")
        au._apply = fake
