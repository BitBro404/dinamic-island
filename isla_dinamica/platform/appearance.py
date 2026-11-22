"""Modo oscuro y luz nocturna según el escritorio; el portal sirve para LEER el color del sistema.

Cada método devuelve un backend con `get()`, `set(bool)`, `watch(cb)` y `readonly`. Así el servicio no
sabe si el cambio se hace con gsettings, con una orden o desde la extensión de GNOME.
"""
import os
import re
import subprocess

from gi.repository import Gio, GLib

from .chain import Method, Tools, pick
from .desktop import detect

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


def parse_color_scheme(value):
    """Portal: 1 = oscuro, 0/2 = claro."""
    try:
        return int(value) == 1
    except (TypeError, ValueError):
        return False


def portal_color_scheme(bus):
    try:
        v = bus.call_sync(PORTAL_BUS, PORTAL_PATH, "org.freedesktop.portal.Settings", "Read",
                          GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                          GLib.VariantType("(v)"), 0, 1000, None).unpack()[0]
        return parse_color_scheme(v.unpack() if hasattr(v, "unpack") else v)
    except (GLib.Error, AttributeError, TypeError):
        return False


class SettingsAppearance:
    """Una clave de gsettings (cadena o booleana)."""

    def __init__(self, settings, schema, key, kind="string", on="prefer-dark", off="default", invert=False):
        self.s = settings(schema) if callable(settings) else settings
        self.key, self.kind, self.on, self.off, self.invert = key, kind, on, off, invert
        self.readonly = False

    def get(self):
        v = self.s.get_string(self.key) if self.kind == "string" else self.s.get_boolean(self.key)
        return (v == self.on) if self.kind == "string" else (bool(v) != self.invert)

    def set(self, value):
        if self.kind == "string":
            self.s.set_string(self.key, self.on if value else self.off)
            if self.key == "color-scheme":     # los temas GTK suelen tener una variante -dark
                theme = self.s.get_string("gtk-theme")
                base = re.sub(r"-(dark|darkest|light)$", "", theme)
                cand = base + "-dark" if value else base
                dirs = ["/usr/share/themes", os.path.expanduser("~/.themes"),
                        os.path.expanduser("~/.local/share/themes")]
                if cand != theme and any(os.path.isdir(os.path.join(d, cand)) for d in dirs):
                    self.s.set_string("gtk-theme", cand)
        else:
            self.s.set_boolean(self.key, (not value) if self.invert else value)

    def watch(self, cb):
        self.s.connect("changed::" + self.key, lambda *_: cb())


class PortalDark:
    """El portal xdg-desktop-portal solo permite LEER el esquema de colores."""

    def __init__(self, bus):
        self.bus, self.readonly = bus, True

    def get(self):
        return portal_color_scheme(self.bus)

    def set(self, _value):
        pass

    def watch(self, cb):
        try:
            self.bus.signal_subscribe(PORTAL_BUS, "org.freedesktop.portal.Settings", "SettingChanged",
                                      PORTAL_PATH, None, Gio.DBusSignalFlags.NONE,
                                      lambda *_: cb())
        except GLib.Error:
            pass


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class CommandAppearance:
    """Alternar con una orden (KDE, redshift/gammastep…):_err no bloquea la interfaz."""

    def __init__(self, get_argv, set_argv, enabled=lambda out: bool((out or "").strip())):
        self.get_argv, self.set_argv, self._enabled = get_argv, set_argv, enabled
        self.readonly = False

    def get(self):
        return self._enabled(_run(self.get_argv))

    def set(self, value):
        for argv in self.set_argv(value):
            _run(argv)

    def watch(self, cb):
        pass                     # estos backends se consultan al abrir el panel


def _kde_dark():
    def set_(on):
        scheme = "Breeze Dark" if on else "Breeze"
        return [["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme", scheme],
                ["qdbus6", "org.kde.KGlobalSettings", "/kglobalSettings", "org.kde.KGlobalSettings",
                 "notifyChange", "5", "0"]]
    return CommandAppearance(["kreadconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"],
                             set_, lambda out: "dark" in (out or "").lower())


def _gamma(cmd):
    return CommandAppearance(["pgrep", "-x", cmd],
                             lambda on: ([cmd, "-b", "0.8"] + ([] if on else [])) if on else [["pkill", "-x", cmd]],
                             lambda out: bool((out or "").strip()))


DARK_METHODS = [
    Method("GNOME color-scheme", lambda t, d: t.has_schema("org.gnome.desktop.interface"),
           lambda bus, s: SettingsAppearance(s, "org.gnome.desktop.interface", "color-scheme")),
    Method("Cinnamon theme", lambda t, d: t.has_schema("org.cinnamon.desktop.interface"),
           lambda bus, s: SettingsAppearance(s, "org.cinnamon.desktop.interface", "gtk-theme",
                                             on="Adwaita-dark", off="Adwaita")),
    Method("KDE ColorScheme", lambda t, d: t.has("kwriteconfig6", "qdbus6"), lambda bus, s: _kde_dark(),
           hint="kde-config-gtk-style"),
    Method("portal (solo lectura)", lambda t, d: True, lambda bus, s: PortalDark(bus)),
]

NIGHT_METHODS = [
    Method("GNOME night light", lambda t, d: t.has_schema("org.gnome.settings-daemon.plugins.color"),
           lambda bus, s: SettingsAppearance(s, "org.gnome.settings-daemon.plugins.color",
                                             "night-light-enabled", kind="bool")),
    Method("gammastep", lambda t, d: t.has("gammastep"), lambda bus, s: _gamma("gammastep"), hint="gammastep"),
    Method("redshift", lambda t, d: t.has("redshift"), lambda bus, s: _gamma("redshift"), hint="redshift"),
]
DARK_FEATURE = ("Modo oscuro", DARK_METHODS)
NIGHT_FEATURE = ("Luz nocturna", NIGHT_METHODS)


class Appearance:
    """Modo oscuro y luz nocturna con las cadenas anteriores, sin nombres de escritorio fuera de platform/."""

    def __init__(self, on_change, tools=None, desktop=None, bus=None, settings=None,
                 dark_methods=DARK_METHODS, night_methods=NIGHT_METHODS):
        tools, desktop = tools or Tools(), desktop or detect(os.environ)
        self._settings = settings or (lambda schema: Gio.Settings.new(schema))
        self._bus, self.on_change = bus, on_change
        dm, nm = pick(dark_methods, tools, desktop), pick(night_methods, tools, desktop)
        self._dark = dm.act(bus, self._settings) if dm else None
        self._night = nm.act(bus, self._settings) if nm else None
        self.has_dark, self.has_night = self._dark is not None, self._night is not None
        self.dark_name, self.night_name = dm.name if dm else "", nm.name if nm else ""
        for backend in (self._dark, self._night):
            if backend:
                backend.watch(on_change)

    @property
    def dark(self):
        return bool(self._dark and self._dark.get())

    @property
    def night(self):
        return bool(self._night and self._night.get())

    def toggle_dark(self):
        return self._toggle(self._dark)

    def toggle_night(self):
        return self._toggle(self._night)

    @staticmethod
    def _toggle(backend):
        if not backend or backend.readonly:
            return False
        backend.set(not backend.get())
        return True
