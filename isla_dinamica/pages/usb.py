"""Medios extraíbles."""
from gi.repository import Gio, Gtk

from ..ui.gtk import button, clear, icon
from .base import Page
from .registry import page


class UsbPage(Page):
    """USB: unidades conectadas, abrir y expulsar."""
    PAGES = {
        "usb": page("_build_usb", "_fill_usb", ("usb",), "_open_usb"),
    }

    def _build_usb(self):
        box = self._page("Medios extraíbles")
        self.u_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.u_list, 250), False, False, 0)
        return box

    def _fill_usb(self):
        c = self.core
        clear(self.u_list)
        vols = c.drives.items()
        for v in vols:
            gicon = v.get_symbolic_icon()
            names = gicon.get_names() if isinstance(gicon, Gio.ThemedIcon) else []
            mounted = v.get_mount() is not None
            ej = button("ctrl", icon("media-eject-symbolic"), lambda v=v: c.drives.eject(v), "Expulsar")
            self.u_list.pack_start(self._row(names[0] if names else "drive-removable-media-symbolic",
                                             v.get_name(),
                                             "Montado · clic para abrir" if mounted else "Clic para montar y abrir",
                                             lambda v=v: (self._set_hover(False), c.drives.open(v)), [ej]),
                                   False, False, 0)
        if not vols:
            self._empty(self.u_list, "No hay medios extraíbles conectados")
        self.u_list.show_all()

    def _open_usb(self):
        self.core.radios.refresh()
