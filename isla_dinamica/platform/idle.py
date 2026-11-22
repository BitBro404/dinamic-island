"""Detectar inactividad con lo que haya: proceso (swayidle) o sondeo (X11, GNOME, KDE).

Las dos formas tienen la misma interfaz (`on_idle(ts)`, `on_active(ts)`) y la misma señal de cambio de
umbral (`set_after`). En wlroots se mantiene swayidle con ext-idle-notify; en X11 se consulta
XScreenSaver directamente por ctypes (sin xprintidle) y en GNOME/KDE el reloj de inactividad del bus.
"""
import ctypes
import os
import subprocess
import threading
import time

from gi.repository import GLib, Gio

from ..util.proc import dbg, tied
from .chain import Method, Tools, pick
from .desktop import detect
from .shell import BUS as SHELL_BUS


class _XScreenSaverInfo(ctypes.Structure):
    _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int), ("kind", ctypes.c_int),
                ("idle", ctypes.c_ulong), ("event_mask", ctypes.c_ulong)]


def x11_idle_ms():
    """Milisegundos sin input según libXss, o None si no se puede saber."""
    try:
        xss = ctypes.CDLL("libXss.so.1")
        xss.XOpenDisplay.restype = ctypes.c_void_p
        xss.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        xss.XDefaultRootWindow.restype = ctypes.c_ulong
        xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                              ctypes.POINTER(_XScreenSaverInfo)]
        xss.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = xss.XOpenDisplay(None)
        if not display:
            return None
        try:
            info = _XScreenSaverInfo()
            if xss.XScreenSaverQueryInfo(display, xss.XDefaultRootWindow(display), ctypes.byref(info)):
                return int(info.idle)
        finally:
            xss.XCloseDisplay(display)
    except (OSError, AttributeError, TypeError):
        pass
    return None


def gnome_idle_ms(bus):
    try:
        value = bus.call_sync("org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
                              "org.gnome.Mutter.IdleMonitor", "GetIdletime", None,
                              GLib.VariantType("(x)"), 0, 500, None).unpack()[0]
        return int(value)
    except (GLib.Error, AttributeError, TypeError):
        return 0


def kde_idle_ms(bus):
    try:
        secs = bus.call_sync("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver",
                             "GetSessionIdleTime", None, GLib.VariantType("(u)"), 0, 500, None).unpack()[0]
        return int(secs) * 1000
    except (GLib.Error, AttributeError, TypeError):
        return 0


METHODS = [
    Method("swayidle", lambda t, d: d.wlr and t.has("swayidle"), "process", hint="swayidle"),
    Method("GNOME IdleMonitor", lambda t, d: d.family == "gnome" and
           (t.has_name("org.gnome.Mutter.IdleMonitor") or t.has_name(SHELL_BUS)), "poll"),
    Method("KDE ScreenSaver", lambda t, d: d.family == "kde" and t.has_name("org.freedesktop.ScreenSaver"),
           "poll"),
    Method("XScreenSaver", lambda t, d: d.x11 or d.xwayland, "poll", hint="libxss1"),
]
FEATURE = ("Inactividad", METHODS)


def poll_step(after, was_idle, idle_ms):
    """¿Debe cambiar el estado? Función pura: umbral en ms y estado anterior."""
    return (idle_ms or 0) >= after * 1000


def _spawn(argv):
    return subprocess.Popen(tied(argv), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1)


class IdleWatch:
    """Avisa cuando no hay teclado/ratón durante `after` segundos y cuando vuelve."""

    def __init__(self, after, on_idle, on_active, tools=None, desktop=None, bus=None, methods=METHODS,
                 idle_ms=None, clock=time.monotonic, spawn=None, sleep=None, start=True):
        self.after, self.on_idle, self.on_active = after, on_idle, on_active
        self.clock, self.sleep, self._spawn = clock, sleep or time.sleep, spawn or _spawn
        self.method = pick(methods, tools or Tools(), desktop or detect(os.environ))
        self.mode = self.method.act if self.method else None
        self.supported = self.method is not None
        self.error = None if self.supported else "Sin forma de medir inactividad en este escritorio"
        self.proc, self._restart, self._idle = None, False, False
        self.idle_ms = idle_ms or self._default_idle_ms(bus, desktop)
        if start:
            if self.mode == "process":
                threading.Thread(target=self._loop, daemon=True).start()
            elif self.mode == "poll":
                threading.Thread(target=self._poll_loop, daemon=True).start()
            else:
                self.on_active(self.clock())

    def _default_idle_ms(self, bus, desktop):
        d = desktop or detect(os.environ)
        if d.family in ("gnome", "kde"):
            bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            return gnome_idle_ms if d.family == "gnome" else lambda: kde_idle_ms(bus)
        return x11_idle_ms

    @staticmethod
    def command(after):
        return ["swayidle", "-w", "timeout", str(int(after)), "echo idle", "resume", "echo active"]

    @staticmethod
    def parse_line(line):
        word = (line or "").strip()
        return word if word in ("idle", "active") else None

    def set_after(self, after):
        """Cambia el umbral: en modo proceso hay que reiniciar swayidle; en sondeo basta con el valor."""
        self.after = after
        self._restart = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def poll_step(self, now=None, ms=None):
        if now is None:
            now = self.clock()
        if ms is None:
            ms = self.idle_ms()
        idle = poll_step(self.after, self._idle, ms)
        if idle != self._idle:
            self._idle = idle
            (self.on_idle if idle else self.on_active)(now)
        return idle

    def _poll_loop(self):
        while True:
            try:
                self.poll_step()
            except Exception as e:
                dbg("presence", e)
            self.sleep(2)

    def _loop(self):
        while True:
            try:
                self.proc = self._spawn(self.command(self.after))
                self.error = None
                for line in self.proc.stdout:
                    kind = self.parse_line(line)
                    if kind == "idle":
                        self.on_idle(time.monotonic())
                    elif kind == "active":
                        self.on_active(time.monotonic())
                self.proc.wait()
            except OSError as e:
                self.error = f"No se pudo lanzar swayidle: {e}"
            self.on_active(time.monotonic())     # sin datos fiables: tratar como si hubiera input
            if not self._restart:
                time.sleep(5)
            self._restart = False
