"""Grabación de pantalla: el método lo elige `platform/record.py`; aquí solo se gestiona el estado."""
import os
import signal
import subprocess
import threading
import time

from gi.repository import GLib, Gio

from ..platform.chain import Tools
from ..platform.record import PORTAL_BUS, PORTAL_PATH, SHELL_BUS, SHELL_PATH, build, choose
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
    """Grabación de pantalla (wf-recorder, ffmpeg, extensión GNOME o portal) con estado y duración."""
    AUDIO = (("none", "Sin audio"), ("mic", "Micrófono"), ("system", "Sonido del equipo"))

    def __init__(self, on_change, on_done, desktop=None, tools=None):
        self.on_change, self.on_done = on_change, on_done
        self.method = choose(tools or Tools(), desktop)
        self.available = self.method is not None
        self.kind = self.method.act[0] if self.method else None
        self.proc = None
        self.path = None
        self.started = None
        self.audio = "none"
        self.error = None
        self._session = None
        self._portal_fd = None

    @property
    def active(self):
        return self.started is not None

    def elapsed(self):
        return time.monotonic() - self.started if self.started else 0

    @staticmethod
    def _bus():
        return Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def _finish(self, ok, err=""):
        proc, secs = self.proc, self.elapsed()
        self.proc, self.started = None, None
        if proc:
            try:
                err = (proc.stderr.read()[-400:] if proc.stderr else "") or err
            except (OSError, ValueError):
                pass
        ok = ok and bool(self.path) and os.path.exists(self.path) and os.path.getsize(self.path) > 1024
        if not ok:
            self.error = (err.strip().splitlines() or ["No se pudo grabar"])[-1]
            dbg("rec error:", err)
            try:
                if self.path and os.path.exists(self.path):
                    os.remove(self.path)
            except OSError:
                pass
        self.on_change()
        self.on_done(self.path if ok else None, secs)

    def start(self, geometry, audio=None):
        """geometry: «x,y WxH» en coordenadas lógicas."""
        if self.proc or self.started or not self.available:
            return False
        audio = audio or self.audio
        folder = videos_dir()
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, time.strftime("Grabación %Y-%m-%d %H-%M-%S.mp4"))
        device = _audio_device(audio) if audio != "none" else None
        try:
            if self.kind == "cmd":
                argv = build(self.method, geometry, self.path, device, os.environ.get("DISPLAY", ":0"))
                dbg("rec:", argv)
                self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.PIPE, text=True)
                GLib.child_watch_add(GLib.PRIORITY_DEFAULT, self.proc.pid, self._exited)
            elif self.kind == "dbus":
                self._bus().call(SHELL_BUS, SHELL_PATH, SHELL_BUS, "Screencast",
                                 GLib.Variant("(ss)", (self.path, geometry or "")), None, 0, 2000, None,
                                 lambda *_: GLib.timeout_add(1000, self._check_db_file))
            else:
                self._portal_start()
        except (OSError, GLib.Error) as e:
            self.error, self.proc = str(e), None
            self.on_change()
            return False
        self.error, self.started, self.audio = None, time.monotonic(), audio
        self.on_change()
        return True

    def _check_db_file(self):
        """La extensión guarda por su cuenta: comprobamos el archivo hasta que exista o se detenga."""
        if not self.started:
            return False
        if self.path and os.path.exists(self.path) and os.path.getsize(self.path) > 1024:
            self._finish(True)
            return False
        return True

    def _portal_start(self):
        """Portal de pantalla: sesión, fuentes y Start con un fd donde el portal escribe el vídeo."""
        bus = self._bus()
        token = f"isla_{int(time.time())}"
        bus.call(PORTAL_BUS, PORTAL_PATH, "org.freedesktop.portal.ScreenCast", "CreateSession",
                 GLib.Variant("(a{sv})", ({"session_handle_token": GLib.Variant("s", token)},)),
                 GLib.VariantType("(o)"), 0, 5000, None, self._portal_created)
        bus.signal_subscribe(PORTAL_BUS, "org.freedesktop.portal.Request", "Response",
                             PORTAL_PATH, None, Gio.DBusSignalFlags.NONE, self._portal_response)

    def _portal_created(self, source, res):
        try:
            self._session = source.call_finish(res).unpack()[0]
        except GLib.Error as e:
            self.error = str(e)
            return
        bus = self._bus()
        opts = {"types": GLib.Variant("u", 3)}       # monitor (1) o ventana (2)
        bus.call(PORTAL_BUS, PORTAL_PATH, "org.freedesktop.portal.ScreenCast", "SelectSources",
                 GLib.Variant("(oa{sv})", (self._session, opts)), GLib.VariantType("(o)"), 0, 5000, None,
                 lambda *_: None)

    def _portal_response(self, *_args):
        """El usuario eligió la fuente: arrancamos con un pipe que volcamos a `self.path`."""
        if not self.started or self._portal_fd or not self._session:
            return
        read_fd, write_fd = os.pipe()
        fds = Gio.UnixFDList.new()
        fds.append(write_fd)
        os.close(write_fd)
        self._portal_fd = read_fd
        bus = self._bus()
        bus.call_with_unix_fd_list(PORTAL_BUS, PORTAL_PATH, "org.freedesktop.portal.ScreenCast", "Start",
                                   GLib.Variant("(ooa{sv})", (self._session, "", {})),
                                   GLib.VariantType("(o)"), 0, 5000, fds, None, lambda *_: None)
        threading.Thread(target=self._portal_copy, args=(read_fd,), daemon=True).start()

    def _portal_copy(self, fd):
        try:
            with open(self.path, "wb") as out:
                while True:
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        break
                    out.write(chunk)
        except OSError:
            pass
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
            if self._portal_fd == fd:
                self._portal_fd = None
            GLib.idle_add(lambda: (self._finish(bool(self.started)), False)[1])

    def stop(self):
        if not self.active:
            return
        if self.kind == "cmd" and self.proc and self.proc.poll() is None:
            try:
                self.proc.send_signal(signal.SIGINT)
            except OSError:
                pass
        elif self.kind == "dbus":
            try:
                self._bus().call(SHELL_BUS, SHELL_PATH, SHELL_BUS, "StopScreencast", None, None, 0, 2000, None,
                                 lambda *_: None)
            except GLib.Error:
                pass
            self._finish(True)
        elif self.kind == "portal" and self._session:
            try:
                self._bus().call(PORTAL_BUS, self._session, "org.freedesktop.portal.Session", "Close",
                                 None, None, 0, 2000, None, lambda *_: None)
            except GLib.Error:
                pass

    def _exited(self, _pid, status):
        self._finish(True)
