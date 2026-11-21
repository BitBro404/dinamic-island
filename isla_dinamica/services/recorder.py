"""Grabación de pantalla con wf-recorder (pantalla completa o un área, con o sin audio)."""
import signal

import os
import subprocess
import time

from gi.repository import GLib

from ..util.proc import dbg


def videos_dir():
    base = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS) or os.path.expanduser("~/Vídeos")
    return os.path.join(base, "Grabaciones")


def _audio_device(kind):
    """«mic» → fuente por defecto; «system» → monitor de la salida por defecto."""
    try:
        if kind == "mic":
            return subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True,
                                  timeout=3).stdout.strip() or None
        sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True,
                              timeout=3).stdout.strip()
        return sink + ".monitor" if sink else None
    except (OSError, subprocess.SubprocessError):
        return None


class Recorder:
    """Grabación de pantalla (wf-recorder) con estado y duración."""
    AUDIO = (("none", "Sin audio"), ("mic", "Micrófono"), ("system", "Sonido del equipo"))

    def __init__(self, on_change, on_done):
        self.on_change, self.on_done = on_change, on_done
        self.available = bool(GLib.find_program_in_path("wf-recorder"))
        self.proc = None
        self.path = None
        self.started = None
        self.audio = "none"
        self.error = None

    @property
    def active(self):
        return self.proc is not None

    def elapsed(self):
        return time.monotonic() - self.started if self.started else 0

    def start(self, geometry, audio=None):
        """geometry: «x,y WxH» en coordenadas lógicas."""
        if self.proc or not self.available:
            return False
        audio = audio or self.audio
        folder = videos_dir()
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, time.strftime("Grabación %Y-%m-%d %H-%M-%S.mp4"))
        argv = ["wf-recorder", "-y", "-g", geometry, "-f", self.path,
                "-c", "libx264", "-p", "preset=veryfast", "-p", "crf=23", "-x", "yuv420p"]
        if audio != "none":
            dev = _audio_device(audio)
            argv.append(f"--audio={dev}" if dev else "--audio")
        # si la isla muere, SIGINT para que wf-recorder cierre bien el archivo
        if GLib.find_program_in_path("setpriv"):
            argv = ["setpriv", "--pdeathsig", "INT", "--"] + argv
        dbg("rec:", argv)
        try:
            self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.PIPE, text=True)
        except OSError as e:
            self.error, self.proc = str(e), None
            self.on_change()
            return False
        self.error, self.started, self.audio = None, time.monotonic(), audio
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, self.proc.pid, self._exited)
        self.on_change()
        return True

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.send_signal(signal.SIGINT)
            except OSError:
                pass

    def _exited(self, _pid, status):
        proc, secs = self.proc, self.elapsed()
        self.proc, self.started = None, None
        err = ""
        try:
            err = proc.stderr.read()[-400:] if proc and proc.stderr else ""
        except (OSError, ValueError):
            pass
        ok = os.path.exists(self.path) and os.path.getsize(self.path) > 1024
        if not ok:
            self.error = (err.strip().splitlines() or ["wf-recorder terminó sin grabar"])[-1]
            dbg("rec error:", status, err)
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
            except OSError:
                pass
        self.on_change()
        self.on_done(self.path if ok else None, secs)
