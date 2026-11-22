"""De dónde salen los avisos del escritorio.

  Budgie (Dispatcher)          señal NotificationAdded del servidor de Budgie (trae el id real);
  D-Bus (cualquier servidor)   se observa la llamada estándar org.freedesktop.Notifications.Notify en el bus de
                               sesión (BecomeMonitor). Funciona con GNOME, Plasma, Cinnamon, XFCE, mako, dunst…
Las dos fuentes entregan el mismo diccionario (`parse_notify`) al callback.
"""
import itertools
import time

from gi.repository import GdkPixbuf, Gio, GLib

from ..util.fmt import strip_markup
from ..util.proc import dbg
from .chain import Method

BUDGIE = ("org.budgie_desktop.Notifications", "/org/budgie_desktop/Notifications",
          "org.buddiesofbudgie.budgie.Dispatcher")
_ids = itertools.count(1_000_000)     # el monitor no ve el id que asigna el servidor: uno propio


def _load_file(path):
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_size(path, 96, 96)
    except GLib.Error:
        return None


def _load_data(data):
    try:
        w, h, stride, alpha, bits, _ch, raw = data
        return GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(raw)), GdkPixbuf.Colorspace.RGB,
                                               alpha, bits, w, h, stride)
    except Exception:
        return None


def parse_notify(app, nid, app_icon, summary, body, hints, now=None, load_file=_load_file,
                 load_data=_load_data):
    """Argumentos de Notify → el aviso que usa la isla. Las imágenes se cargan con funciones inyectables."""
    pb = None
    data = hints.get("image-data") or hints.get("image_data") or hints.get("icon_data")
    if data:
        pb = load_data(data)
    path = hints.get("image-path") or hints.get("image_path") or ""
    if not pb and app_icon and (app_icon.startswith("/") or app_icon.startswith("file://")):
        path = path or app_icon
        app_icon = ""
    if not pb and path:
        pb = load_file(path.replace("file://", ""))
    return {
        "id": nid, "app": app or "Sistema", "icon": app_icon or "preferences-system-notifications-symbolic",
        "pixbuf": pb, "summary": strip_markup(summary), "body": strip_markup(body),
        "desktop": hints.get("desktop-entry") or "", "time": time.time() if now is None else now,
        "urgent": hints.get("urgency") == 2,
    }


class BudgieSource:
    """Avisos del servidor de Budgie (señal propia, con el id real del aviso)."""

    def __init__(self, bus, on_notify):
        self.on_notify = on_notify
        bus.signal_subscribe(None, BUDGIE[2], "NotificationAdded", BUDGIE[1], None, Gio.DBusSignalFlags.NONE,
                             self._added)

    def _added(self, _c, _s, _p, _i, _sig, params):
        app, nid, app_icon, summary, body, _actions, hints, _exp = params.unpack()
        self.on_notify(parse_notify(app, nid, app_icon, summary, body, hints))


class MonitorSource:
    """Observa en el bus de sesión las llamadas Notify (de cualquier app a cualquier servidor).
    Usa una conexión propia: una conexión en modo monitor ya no puede usarse para nada más."""
    RULE = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"

    def __init__(self, bus, on_notify):
        self.on_notify, self.conn = on_notify, None
        try:
            addr = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            self.conn = Gio.DBusConnection.new_for_address_sync(
                addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
                Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self.conn.add_filter(self._filter)
            self.conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.Monitoring",
                                "BecomeMonitor", GLib.Variant("(asu)", ([self.RULE], 0)), None, 0, 2000, None)
        except GLib.Error as e:
            dbg("avisos: el bus no permite observar Notify:", e.message)
            self.conn = None

    def _filter(self, _conn, msg, _incoming):
        # corre en el hilo de GDBus: el trabajo se pasa al bucle principal
        if msg.get_member() == "Notify" and msg.get_interface() == "org.freedesktop.Notifications":
            body = msg.get_body()
            if body is not None and body.n_children() >= 7:
                app, _rid, app_icon, summary, text, _actions, hints = body.unpack()[:7]
                nid = next(_ids)
                GLib.idle_add(lambda: self.on_notify(parse_notify(app, nid, app_icon, summary, text, hints))
                              and False)
        return None                          # el mensaje no sigue a ningún otro filtro


SOURCES = [
    Method("Budgie (Dispatcher)", lambda t, d: t.has_name(BUDGIE[0]), BudgieSource),
    Method("D-Bus (cualquier servidor)", lambda t, d: True, MonitorSource),
]
FEATURE = ("Avisos", SOURCES)
