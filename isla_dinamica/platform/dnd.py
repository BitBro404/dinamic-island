"""«No molestar» y centro de notificaciones, según el servidor de notificaciones que haya.

Cada método tiene la misma interfaz: get() → bool, toggle(), watch(cb) (cb sin argumentos al cambiar; los
que no avisan se consultan cada pocos segundos desde el servicio).
"""
import subprocess

from gi.repository import Gio, GLib

from .chain import Method
from .notify import BUDGIE
from .shell import BUS as SHELL_BUS, PATH as SHELL_PATH


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_bool(out):
    return (out or "").strip().lower() == "true"


def parse_mako(out):
    """`makoctl mode` lista los modos activos, uno por línea."""
    return "do-not-disturb" in (out or "").split()


class BudgieDnd:
    polls = False

    def __init__(self, bus):
        self.bus = bus

    def get(self):
        try:
            return self.bus.call_sync(BUDGIE[0], BUDGIE[1], BUDGIE[2], "GetDoNotDisturb", None,
                                      GLib.VariantType("(b)"), 0, 500, None).unpack()[0]
        except GLib.Error:
            return False

    def toggle(self):
        self.bus.call(BUDGIE[0], BUDGIE[1], BUDGIE[2], "ToggleDoNotDisturb", None, None, 0, 1000, None,
                      lambda *_: None)

    def watch(self, cb):
        self.bus.signal_subscribe(None, BUDGIE[2], "DoNotDisturbChanged", BUDGIE[1], None,
                                  Gio.DBusSignalFlags.NONE, lambda *_: cb())


class SettingsDnd:
    """Una clave booleana de gsettings (GNOME «show-banners» invertida, Cinnamon, MATE)."""
    polls = False

    def __init__(self, schema, key, invert=False, settings=None):
        self.key, self.invert = key, invert
        self.s = settings or Gio.Settings.new(schema)

    def get(self):
        v = self.s.get_boolean(self.key)
        return not v if self.invert else v

    def toggle(self):
        self.s.set_boolean(self.key, self.s.get_boolean(self.key) ^ True)

    def watch(self, cb):
        self.s.connect("changed::" + self.key, lambda *_: cb())


class KdeDnd:
    """Plasma: org.freedesktop.Notifications.Inhibit / UnInhibit y la propiedad Inhibited."""
    polls = True
    DEST, PATH = "org.freedesktop.Notifications", "/org/freedesktop/Notifications"

    def __init__(self, bus):
        self.bus, self.cookie = bus, None

    def get(self):
        try:
            v = self.bus.call_sync(self.DEST, self.PATH, "org.freedesktop.DBus.Properties", "Get",
                                   GLib.Variant("(ss)", (self.DEST, "Inhibited")), GLib.VariantType("(v)"),
                                   0, 500, None).unpack()[0]
            return bool(v)
        except GLib.Error:
            return self.cookie is not None

    def toggle(self):
        try:
            if self.cookie is not None:
                self.bus.call_sync(self.DEST, self.PATH, self.DEST, "UnInhibit", GLib.Variant("(u)", (self.cookie,)),
                                   None, 0, 1000, None)
                self.cookie = None
            else:
                self.cookie = self.bus.call_sync(
                    self.DEST, self.PATH, self.DEST, "Inhibit",
                    GLib.Variant("(ssa{sv})", ("isla-dinamica", "No molestar", {})), GLib.VariantType("(u)"),
                    0, 1000, None).unpack()[0]
        except GLib.Error:
            pass

    def watch(self, cb):
        pass


class CommandDnd:
    """Daemons con su propia herramienta de línea de comandos (mako, SwayNC, dunst, XFCE)."""
    polls = True

    def __init__(self, get_argv, toggle_argv, parse, run=_run):
        self.get_argv, self.toggle_argv, self.parse, self.run = get_argv, toggle_argv, parse, run

    def get(self):
        return self.parse(self.run(self.get_argv))

    def toggle(self):
        self.run(self.toggle_argv)

    def watch(self, cb):
        pass


def _server(*names):
    return lambda t, d: any(n in t.notif_server() for n in names)


XFCE_PROP = ["xfconf-query", "-c", "xfce4-notifyd", "-p", "/do-not-disturb"]

METHODS = [
    Method("Budgie", lambda t, d: t.has_name(BUDGIE[0]), lambda bus: BudgieDnd(bus)),
    Method("GNOME", lambda t, d: _server("gnome-shell")(t, d) and t.has_schema("org.gnome.desktop.notifications"),
           lambda bus: SettingsDnd("org.gnome.desktop.notifications", "show-banners", invert=True)),
    Method("KDE Plasma", _server("plasma", "kde"), lambda bus: KdeDnd(bus)),
    Method("Cinnamon",
           lambda t, d: _server("cinnamon")(t, d) and t.has_schema("org.cinnamon.desktop.notifications"),
           lambda bus: SettingsDnd("org.cinnamon.desktop.notifications", "display-notifications", invert=True)),
    Method("MATE", lambda t, d: _server("notification daemon", "mate")(t, d)
           and t.has_schema("org.mate.NotificationDaemon"),
           lambda bus: SettingsDnd("org.mate.NotificationDaemon", "do-not-disturb")),
    Method("XFCE", lambda t, d: _server("xfce4-notifyd")(t, d) and t.has("xfconf-query"),
           lambda bus: CommandDnd(XFCE_PROP, XFCE_PROP + ["-T"], parse_bool), hint="xfconf"),
    Method("mako", lambda t, d: _server("mako")(t, d) and t.has("makoctl"),
           lambda bus: CommandDnd(["makoctl", "mode"], ["makoctl", "mode", "-t", "do-not-disturb"], parse_mako)),
    Method("SwayNC", lambda t, d: _server("swaync")(t, d) and t.has("swaync-client"),
           lambda bus: CommandDnd(["swaync-client", "-D", "-sw"], ["swaync-client", "-d", "-sw"], parse_bool)),
    Method("dunst", lambda t, d: _server("dunst")(t, d) and t.has("dunstctl"),
           lambda bus: CommandDnd(["dunstctl", "is-paused"], ["dunstctl", "set-paused", "toggle"], parse_bool)),
]
FEATURE = ("No molestar", METHODS)


def _call(bus, dest, path, iface, method):
    bus.call(dest, path, iface, method, None, None, 0, 1000, None, lambda *_: None)


# abrir el centro de notificaciones (si no hay método, el botón se oculta)
CENTER = [
    Method("Budgie Raven", lambda t, d: t.has_name("org.budgie_desktop.Raven"),
           lambda bus: _call(bus, "org.budgie_desktop.Raven", "/org/budgie_desktop/Raven",
                             "org.budgie_desktop.Raven", "ToggleNotificationsView")),
    Method("SwayNC", lambda t, d: _server("swaync")(t, d) and t.has("swaync-client"),
           lambda bus: _run(["swaync-client", "-t", "-sw"])),
    Method("GNOME (extensión de la isla)",
           lambda t, d: t.has_name(SHELL_BUS),
           lambda bus: _call(bus, SHELL_BUS, SHELL_PATH, SHELL_BUS, "ToggleNotificationCenter")),
]
CENTER_FEATURE = ("Centro de avisos", CENTER)
