"""¿Quién usa la cámara o el micrófono? (como los puntos de privacidad del iPhone)."""
import json
import os
import subprocess
import threading
import time

from gi.repository import GLib

_PIPEWIRE = ("pipewire", "wireplumber", "pipewire-pulse")
_NAMES = {"chrome": "Chrome", "google-chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox",
          "teams": "Teams", "zoom": "Zoom", "obs": "OBS", "discord": "Discord", "slack": "Slack"}


def _pretty(name):
    n = (name or "").strip()
    return _NAMES.get(n.lower(), n[:1].upper() + n[1:] if n else "Una app")


def camera_users(proc="/proc"):
    """Procesos con /dev/video* abierto (solo los del usuario; ~10 ms).
    La propia isla no cuenta: el sensor de presencia abre la cámara unos instantes."""
    users = set()
    me = str(os.getpid())
    for pid in os.listdir(proc):
        if not pid.isdigit() or pid == me:
            continue
        try:
            with os.scandir(f"{proc}/{pid}/fd") as fds:
                for fd in fds:
                    try:
                        if os.readlink(fd.path).startswith("/dev/video"):
                            with open(f"{proc}/{pid}/comm") as f:
                                users.add(f.read().strip())
                            break
                    except OSError:
                        pass
        except OSError:
            pass
    named = {u for u in users if u not in _PIPEWIRE}
    if users and not named:
        named = {"una app (vía PipeWire)"}
    return sorted(_pretty(u) for u in named)


def mic_users():
    """Apps grabando del micrófono, según PipeWire/PulseAudio."""
    try:
        out = subprocess.run(["pactl", "-f", "json", "list", "source-outputs"], capture_output=True,
                             text=True, timeout=3).stdout
        streams = json.loads(out or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    apps = set()
    for s in streams:
        p = s.get("properties", {})
        if s.get("corked") or "peak detect" in (p.get("media.name") or "").lower():
            continue          # pausado, o medidores de volumen (pavucontrol)
        if (p.get("stream.capture.sink") == "true" or
                str(p.get("target.object", "")).endswith(".monitor")):
            continue          # graba lo que suena, no el micrófono
        apps.add(_pretty(p.get("application.name") or p.get("application.process.binary")))
    return sorted(apps)


class Privacy:
    """Revisa cada 3 s en un hilo aparte; avisa al empezar a usarse."""

    def __init__(self, on_change, on_start, enabled=lambda: True):
        self.on_change, self.on_start, self.enabled = on_change, on_start, enabled
        self.cam, self.mic = [], []
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            if self.enabled():
                cam, mic = camera_users(), mic_users()
            else:
                cam, mic = [], []
            GLib.idle_add(self._update, cam, mic)
            time.sleep(3)

    def _update(self, cam, mic):
        if cam != self.cam or mic != self.mic:
            if cam and not self.cam:
                self.on_start("cam", cam)
            if mic and not self.mic:
                self.on_start("mic", mic)
            self.cam, self.mic = cam, mic
            self.on_change()
        return False

    def summary(self):
        bits = []
        if self.cam:
            bits.append("Cámara: " + ", ".join(self.cam))
        if self.mic:
            bits.append("Micrófono: " + ", ".join(self.mic))
        return " · ".join(bits)
