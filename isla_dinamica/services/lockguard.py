"""Bloqueo de sesión: mientras la sesión esté bloqueada, la isla se oculta.

La isla es una capa «overlay» de Wayland: si el bloqueador de pantalla no usa ext-session-lock, podría
dibujarse (y usarse: avisos, portapapeles, Wi-Fi, apagar…) encima de la pantalla de bloqueo.
`LockGuard` es la lógica pura (testeable) y `watch_session_lock` la conecta a logind por D-Bus.
"""
import os

from gi.repository import Gio, GLib

LOGIN1 = "org.freedesktop.login1"


class LockGuard:
    """Decide si la isla se ve. `set_visible(bool)` muestra u oculta las ventanas; `on_lock()` borra datos
    sensibles en memoria (portapapeles). Las ocultaciones temporales (captura, grabación) pasan por
    `request_visible`, que nunca vuelve a mostrar la isla mientras haya bloqueo."""

    def __init__(self, set_visible, on_lock=lambda: None):
        self.set_visible, self.on_lock = set_visible, on_lock
        self.locked = False

    def set_locked(self, locked):
        locked = bool(locked)
        if locked == self.locked:
            return
        self.locked = locked
        self.set_visible(not locked)
        if locked:
            self.on_lock()

    def request_visible(self, visible):
        if visible and self.locked:
            return
        self.set_visible(visible)


def _session_path(sysbus):
    """Ruta D-Bus de la sesión gráfica del usuario (la «Display» de logind). La isla puede no
    pertenecer a ninguna sesión (lanzada con setsid), así que no sirve GetSessionByPID."""
    try:
        user = sysbus.call_sync(LOGIN1, "/org/freedesktop/login1", f"{LOGIN1}.Manager", "GetUser",
                                GLib.Variant("(u)", (os.getuid(),)), None, 0, 3000, None).unpack()[0]
        disp = sysbus.call_sync(LOGIN1, user, "org.freedesktop.DBus.Properties", "Get",
                                GLib.Variant("(ss)", (f"{LOGIN1}.User", "Display")), None, 0, 3000, None)
        return disp.unpack()[0][1]
    except GLib.Error:
        return None


def watch_session_lock(sysbus, guard, on_unlock=lambda: None):
    """Conecta `guard` a logind: señales Lock/Unlock y la propiedad LockedHint de nuestra sesión."""
    path = _session_path(sysbus)
    if not path or path == "/":
        return None

    def lock(*_):
        guard.set_locked(True)

    def unlock(*_):
        was = guard.locked
        guard.set_locked(False)
        if was:
            on_unlock()

    def props(_c, _s, _p, _i, _sig, params):
        iface, changed, _inv = params.unpack()
        if iface == f"{LOGIN1}.Session" and "LockedHint" in changed:
            (lock if changed["LockedHint"] else unlock)()

    sysbus.signal_subscribe(LOGIN1, f"{LOGIN1}.Session", "Lock", path, None, Gio.DBusSignalFlags.NONE, lock)
    sysbus.signal_subscribe(LOGIN1, f"{LOGIN1}.Session", "Unlock", path, None, Gio.DBusSignalFlags.NONE, unlock)
    sysbus.signal_subscribe(LOGIN1, "org.freedesktop.DBus.Properties", "PropertiesChanged", path, None,
                            Gio.DBusSignalFlags.NONE, props)
    return path
