"""Notificaciones del escritorio."""
from ..common import *  # noqa: F401,F403


class Notifications:
    """Escucha las notificaciones que recibe el servidor de Budgie (Teams, correo, sistema...)."""
    DEST, PATH, IFACE = "org.budgie_desktop.Notifications", "/org/budgie_desktop/Notifications", \
        "org.buddiesofbudgie.budgie.Dispatcher"

    def __init__(self, bus, on_notify, on_dnd):
        self.bus, self.on_notify, self.on_dnd = bus, on_notify, on_dnd
        self.dnd = False
        bus.signal_subscribe(None, self.IFACE, "NotificationAdded", self.PATH, None,
                             Gio.DBusSignalFlags.NONE, self._added)
        bus.signal_subscribe(None, self.IFACE, "DoNotDisturbChanged", self.PATH, None,
                             Gio.DBusSignalFlags.NONE, self._dnd_changed)
        try:
            self.dnd = bus.call_sync(self.DEST, self.PATH, self.IFACE, "GetDoNotDisturb", None,
                                     GLib.VariantType("(b)"), 0, 500, None).unpack()[0]
        except GLib.Error:
            pass

    def _added(self, _c, _s, _p, _i, _sig, params):
        app, nid, app_icon, summary, body, _actions, hints, _exp = params.unpack()
        pb = None
        data = hints.get("image-data") or hints.get("image_data") or hints.get("icon_data")
        if data:
            try:
                w, h, stride, alpha, bits, _ch, raw = data
                pb = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(raw)), GdkPixbuf.Colorspace.RGB,
                                                     alpha, bits, w, h, stride)
            except Exception:
                pb = None
        path = hints.get("image-path") or hints.get("image_path") or ""
        if not pb and app_icon and (app_icon.startswith("/") or app_icon.startswith("file://")):
            path = path or app_icon
            app_icon = ""
        if not pb and path:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path.replace("file://", ""), 96, 96)
            except GLib.Error:
                pb = None
        self.on_notify({
            "id": nid, "app": app or "Sistema", "icon": app_icon or "preferences-system-notifications-symbolic",
            "pixbuf": pb, "summary": strip_markup(summary), "body": strip_markup(body),
            "desktop": hints.get("desktop-entry") or "", "time": time.time(),
            "urgent": hints.get("urgency") == 2,
        })

    def _dnd_changed(self, _c, _s, _p, _i, _sig, params):
        self.dnd = params.unpack()[0]
        self.on_dnd()

    def toggle_dnd(self):
        self.bus.call(self.DEST, self.PATH, self.IFACE, "ToggleDoNotDisturb", None, None, 0, 1000, None,
                      lambda *_: None)

    def open_center(self):
        self.bus.call("org.budgie_desktop.Raven", "/org/budgie_desktop/Raven", "org.budgie_desktop.Raven",
                      "ToggleNotificationsView", None, None, 0, 1000, None, lambda *_: None)
