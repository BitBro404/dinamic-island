"""Consume un núcleo entero durante 55 s (para probar el aviso de «usa mucha CPU»)."""
import subprocess


def setup(core):
    core.config.save = lambda: None
    subprocess.Popen(["timeout", "55", "python3", "-c", "while True: pass"])
