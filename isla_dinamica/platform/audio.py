"""Volumen y sonidos de aviso con WirePlumber/PulseAudio o solo PulseAudio.

Mantiene la lectura y las acciones en argv para probarlas sin servidor de audio. `parse_volume` entiende
tanto la salida de `wpctl` (0.45 [MUTED]) como la de `pactl` (45% / Mute: yes).
"""
import os
import re

from .chain import Method, Tools, pick
from .desktop import detect

VOLUME_METHODS = [
    Method("wpctl", lambda t, d: t.has("wpctl"), ("wpctl", "wpctl")),
    Method("pactl", lambda t, d: t.has("pactl"), ("pactl", "pactl")),
]
SOUND_METHODS = [
    Method("pw-play", lambda t, d: t.has("pw-play"), ("pw-play", "{}")),
    Method("paplay", lambda t, d: t.has("paplay"), ("paplay", "{}")),
    Method("canberra-gtk-play", lambda t, d: t.has("canberra-gtk-play"), ("canberra-gtk-play", "-f {}")),
]
VOLUME_FEATURE = ("Volumen", VOLUME_METHODS)
SOUND_FEATURE = ("Sonidos", SOUND_METHODS)


def parse_volume(out):
    """«Volume: 0.45 [MUTED]» o «Volume: 45% … Mute: yes» → (0.45, True)."""
    text = out or ""
    percent = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent:
        value = min(1.0, max(0.0, float(percent.group(1)) / 100))
    else:
        decimal = re.search(r"Volume:\s*(\d+(?:\.\d+)?)", text)
        value = min(1.0, max(0.0, float(decimal.group(1)))) if decimal else 0.0
    muted = "MUTED" in text.upper() or bool(re.search(r"Mute:\s*yes", text, re.IGNORECASE))
    return value, muted


def read_command(tools=None, desktop=None):
    m = pick(VOLUME_METHODS, tools or Tools(), desktop or detect(os.environ))
    if not m:
        return None
    return ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"] if m.act[0] == "wpctl" else \
           ["pactl", "get-sink-volume", "@DEFAULT_SINK@"]


def step_argv(up, tools=None, desktop=None):
    m = pick(VOLUME_METHODS, tools or Tools(), desktop or detect(os.environ))
    if not m:
        return None
    if m.act[0] == "wpctl":
        return ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "5%+" if up else "5%-"]
    return ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%" if up else "-5%"]


def set_argv(value, tools=None, desktop=None):
    m = pick(VOLUME_METHODS, tools or Tools(), desktop or detect(os.environ))
    if not m:
        return None
    if m.act[0] == "wpctl":
        return ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{value:.2f}"]
    return ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(value * 100)}%"]


def toggle_mute_argv(tools=None, desktop=None):
    m = pick(VOLUME_METHODS, tools or Tools(), desktop or detect(os.environ))
    if not m:
        return None
    if m.act[0] == "wpctl":
        return ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
    return ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]


def play_argv(path, tools=None, desktop=None):
    m = pick(SOUND_METHODS, tools or Tools(), desktop or detect(os.environ))
    if not m:
        return None
    binary, pattern = m.act
    return [binary] + pattern.format(path).split()
