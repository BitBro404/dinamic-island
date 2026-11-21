"""Casilla redonda de ajustes rápidos (Wi-Fi, Bluetooth, No molestar…) con estado y acceso a su página."""
from gi.repository import Gtk

from ..gtk import button, icon, label, set_class


# ───────────────────────────── casillas de ajustes rápidos ─────────────────────────────
class Tile(Gtk.Box):
    """Ajuste rápido: círculo que activa/desactiva + nombre (que abre el detalle si existe)."""

    def __init__(self, icon_name, title, on_toggle, on_open=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3, halign=Gtk.Align.CENTER)
        self.img = icon(icon_name, px=24)
        self.btn = button("tile", self.img, on_toggle, tooltip=title)
        self.btn.set_halign(Gtk.Align.CENTER)
        self.pack_start(self.btn, False, False, 0)
        if on_open:
            self.name = button("link", cb=on_open, text=title + " ›")
        else:
            self.name = label(title, "dim small", xalign=0.5)
        self.pack_start(self.name, False, False, 0)
        self.sub = label("", "time-small", xalign=0.5)
        self.sub.set_max_width_chars(11)
        self.pack_start(self.sub, False, False, 0)

    def set(self, on, sub="", icon_name=None):
        set_class(self.btn, "on", on)
        if icon_name:
            self.img.set_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
            self.img.set_pixel_size(24)
        self.sub.set_text(sub)
