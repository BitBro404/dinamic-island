"""Bloquear la sesión con el mejor método disponible.

Igual que el resto de `platform/`, los servicios piden «bloquea», no «Budgie». Un método solo cuenta como
éxito si el bloqueador aceptó la orden (D-Bus sin error o comando con código 0); si ninguno lo hace,
`Locker.lock()` devuelve False y quien llama NO debe apagar la pantalla (regla S2).
"""
import os
import subprocess

from gi.repository import GLib

from .chain import Method, Tools, pick
from .desktop import detect


def _dbus_ok(bus, dest, path, iface, method):
    try:
        bus.call_sync(dest, path, iface, method, None, None, 0, 5000, None)
        return True
    except (GLib.Error, OSError):
        return False


def _command_ok(argv):
    try:
        return subprocess.run(argv, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _dbus(dest, path, iface, method="Lock"):
    return lambda bus: lambda: _dbus_ok(bus, dest, path, iface, method)


def _command(argv):
    return lambda bus: lambda: _command_ok(argv)


METHODS = [
    Method("Budgie Screenlock", lambda t, d: t.has_name("org.buddiesofbudgie.BudgieScreenlock"),
           _dbus("org.buddiesofbudgie.BudgieScreenlock", "/org/buddiesofbudgie/Screenlock",
                 "org.buddiesofbudgie.BudgieScreenlock")),
    Method("freedesktop ScreenSaver", lambda t, d: t.has_name("org.freedesktop.ScreenSaver"),
           _dbus("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver")),
    Method("GNOME ScreenSaver", lambda t, d: t.has_name("org.gnome.ScreenSaver"),
           _dbus("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver")),
    Method("Cinnamon ScreenSaver", lambda t, d: t.has_name("org.cinnamon.ScreenSaver"),
           _dbus("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver", "org.cinnamon.ScreenSaver")),
    Method("MATE ScreenSaver", lambda t, d: t.has_name("org.mate.ScreenSaver"),
           _dbus("org.mate.ScreenSaver", "/org/mate/ScreenSaver", "org.mate.ScreenSaver")),
    Method("loginctl", lambda t, d: t.has("loginctl"), _command(["loginctl", "lock-session"]),
           hint="systemd-logind"),
    Method("swaylock", lambda t, d: t.has("swaylock"), _command(["swaylock", "-f"]), hint="swaylock"),
    Method("xdg-screensaver", lambda t, d: t.has("xdg-screensaver"),
           _command(["xdg-screensaver", "lock"]), hint="xdg-utils"),
]
FEATURE = ("Bloqueo", METHODS)


class Locker:
    """Un único bloqueo verificado, o ninguno."""

    def __init__(self, bus, tools=None, desktop=None, methods=METHODS):
        self.method = pick(methods, tools or Tools(), desktop or detect(os.environ))
        self._lock = self.method.act(bus) if self.method else None

    @property
    def supported(self):
        return self._lock is not None

    def lock(self):
        if not self._lock:
            return False
        try:
            return bool(self._lock())
        except Exception:
            return False
