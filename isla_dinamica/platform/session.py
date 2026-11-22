"""Cerrar sesión y mantener despierto, con cadena de métodos por escritorio.

`systemd-inhibit` es el último recurso: guardamos el proceso para poder terminarlo al desactivar el
modo «despierto» (si se pierde, el inhibidor quedaría colgado hasta cerrar la sesión).
"""
import os
import subprocess

from gi.repository import GLib

from .chain import Method, Tools, pick
from .desktop import detect

GNOME = "org.gnome.SessionManager"
GNOME_PATH = "/org/gnome/SessionManager"


def _dbus(dest, path, iface, name, params=None):
    return ("dbus", (dest, path, iface, name, params))


LOGOUT_METHODS = [
    Method("GNOME SessionManager", lambda t, d: t.has_name(GNOME),
           _dbus(GNOME, GNOME_PATH, GNOME, "Logout", 0)),
    Method("KDE ksmserver", lambda t, d: t.has_name("org.kde.ksmserver"),
           _dbus("org.kde.ksmserver", "/KSMServer", "org.kde.KSMServerInterface", "logout", (0, 0, 1))),
    Method("XFCE Session", lambda t, d: t.has("xfce4-session-logout"),
           ("cmd", ["xfce4-session-logout", "--logout"], "xfce4-utils")),
    Method("MATE Session", lambda t, d: t.has_name("org.mate.SessionManager"),
           _dbus("org.mate.SessionManager", "/org/mate/SessionManager", "org.mate.SessionManager", "Logout", 0)),
    Method("loginctl", lambda t, d: True, ("cmd", ["loginctl", "terminate-session"])),
]

INHIBIT_METHODS = [
    Method("GNOME SessionManager", lambda t, d: t.has_name(GNOME), _dbus(GNOME, GNOME_PATH, GNOME, "Inhibit")),
    Method("MATE Session", lambda t, d: t.has_name("org.mate.SessionManager"),
           _dbus("org.mate.SessionManager", "/org/mate/SessionManager", "org.mate.SessionManager", "Inhibit")),
    Method("systemd-inhibit", lambda t, d: t.has("systemd-inhibit"),
           ("cmd", ["systemd-inhibit", "--what=idle", "--why=Isla dinámica", "sleep", "infinity"],
            "systemd")),
]
LOGOUT_FEATURE = ("Cerrar sesión", LOGOUT_METHODS)
INHIBIT_FEATURE = ("Mantener despierto", INHIBIT_METHODS)


def logout_call(method):
    """Argv (cmd) o tupla D-Bus de un método de cierre de sesión."""
    return method.act[1] if method else None


def inhibit_argv(method):
    """Argv de un método «cmd»; None si es D-Bus."""
    return method.act[1] if method and method.act[0] == "cmd" else None


class Session:
    """Cierre de sesión e inhibidor de inactividad con el mejor método disponible."""

    def __init__(self, bus, on_change, tools=None, desktop=None, methods=INHIBIT_METHODS, spawn=None, run=None):
        self.bus, self.on_change, self.method = bus, on_change, pick(methods, tools or Tools(),
                                                                      desktop or detect(os.environ))
        self.kind = self.method.act[0] if self.method else None
        self.cookie, self.proc, self._fallback = None, None, None
        self._spawn = spawn or (lambda argv: subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                                              stderr=subprocess.DEVNULL))
        self._run = run or (lambda argv: subprocess.run(argv, timeout=5, check=False))

    @property
    def supported(self):
        return self.method is not None

    @property
    def awake(self):
        return self.cookie is not None or self.proc is not None

    def logout(self):
        if not self.method:
            return False
        kind, spec = self.method.act[0], self.method.act[1]
        try:
            if kind == "cmd":
                self._run(spec)
            else:
                dest, path, iface, name, params = spec
                self.bus.call(dest, path, iface, name, GLib.Variant("(u)", (params,)) if params is not None else None,
                              None, 0, 2000, None, lambda *_: None)
            return True
        except Exception:
            return False

    def set_awake(self, on):
        if bool(on) == self.awake:
            return True
        if on:
            return self._inhibit()
        return self._uninhibit()

    def _inhibit(self):
        if self.kind == "dbus":
            dest, path, iface, _name, _params = self.method.act[1]
            try:
                v = self.bus.call_sync(dest, path, iface, "Inhibit",
                                       GLib.Variant("(susu)", ("isla-dinamica", 0, "Mantener despierto", 4 | 8)),
                                       GLib.VariantType("(u)"), 0, 1000, None).unpack()[0]
                self.cookie = int(v)
                self.on_change()
                return True
            except Exception:
                pass                          # sin sesión GNOME/MATE: probamos el comando
        self._fallback = next((m for m in INHIBIT_METHODS if m.act[0] == "cmd" and inhibit_argv(m)), None)
        argv = inhibit_argv(self._fallback)
        if not argv:
            return False
        try:
            self.proc = self._spawn(argv)
            self.on_change()
            return True
        except OSError:
            return False

    def _uninhibit(self):
        if self.cookie is not None:
            dest, path, iface, _name, _params = self.method.act[1]
            try:
                self.bus.call(dest, path, iface, "Uninhibit", GLib.Variant("(u)", (self.cookie,)),
                              None, 0, 1000, None, lambda *_: None)
            except Exception:
                pass
            self.cookie = None
        if self.proc:
            try:
                terminate = getattr(self.proc, "terminate", None)
                if terminate:
                    terminate()
            except OSError:
                pass
            self.proc = None
        self.on_change()
        return True
