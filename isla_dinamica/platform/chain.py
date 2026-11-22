"""Cadenas de métodos: cada función del escritorio (bloquear, capturar, …) tiene varios métodos y se usa el
primero disponible (inversión de dependencias: los servicios piden «bloquear», no «Budgie»).

`Tools` agrupa las preguntas al sistema (¿está este comando?, ¿este nombre en el bus?, ¿este esquema de
gsettings?) para que las pruebas las respondan sin escritorio real.
"""
import shutil
from typing import Any, Callable, NamedTuple

from gi.repository import Gio, GLib


def _bus_has_name(name):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                             "NameHasOwner", GLib.Variant("(s)", (name,)), GLib.VariantType("(b)"),
                             0, 500, None).unpack()[0]
    except GLib.Error:
        return False


def _has_schema(schema):
    src = Gio.SettingsSchemaSource.get_default()
    return bool(src and src.lookup(schema, True))


def _notif_server():
    """Nombre del servidor de notificaciones en minúsculas («gnome-shell», «plasma», «mako»…) o ""."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        name = bus.call_sync("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                             "org.freedesktop.Notifications", "GetServerInformation", None,
                             GLib.VariantType("(ssss)"), 0, 1000, None).unpack()[0]
        return (name or "").lower()
    except GLib.Error:
        return ""


class Tools:
    """Preguntas al sistema. Por defecto, las reales; las pruebas pasan funciones falsas."""

    def __init__(self, which=shutil.which, has_name=_bus_has_name, has_schema=_has_schema,
                 notif_server=_notif_server):
        self._which, self._has_name, self._has_schema = which, has_name, has_schema
        self._notif_server, self._server = notif_server, None

    def has(self, *cmds):
        """True si están TODOS los comandos."""
        return all(self._which(c) for c in cmds)

    def has_name(self, bus_name):
        return bool(self._has_name(bus_name))

    def has_schema(self, schema):
        return bool(self._has_schema(schema))

    def notif_server(self):
        """Servidor de notificaciones (se pregunta una vez)."""
        if self._server is None:
            self._server = self._notif_server() or ""
        return self._server


class Method(NamedTuple):
    name: str                                  # lo que muestra --doctor («loginctl», «KDE ScreenSaver»…)
    ok: Callable[[Tools, Any], bool]           # ok(tools, desktop): ¿se puede usar aquí?
    act: Any = None                            # lo que hace (función, argv…; depende de la cadena)
    hint: str = ""                             # paquete que lo haría disponible (para --doctor)


def pick(methods, tools, desktop):
    """El primer método disponible, o None. Un `ok` que falla cuenta como «no disponible»."""
    for m in methods:
        try:
            if m.ok(tools, desktop):
                return m
        except Exception:
            continue
    return None
