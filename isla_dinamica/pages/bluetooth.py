"""Dispositivos Bluetooth."""
from gi.repository import Gtk

from ..ui.gtk import button, clear
from .base import Page
from .registry import feature, page


feature("bt_bubble", "Burbuja Bluetooth",
        "Muestra el dispositivo Bluetooth conectado y su batería como burbuja junto a la píldora")


class BluetoothPage(Page):
    """Bluetooth: encender/apagar y conectar dispositivos emparejados."""
    PAGES = {
        "bt": page("_build_bt", "_fill_bt", ("bt",), "_open_bt"),
    }

    def _build_bt(self):
        self.b_switch = self._switch(self.core.bt.set_powered)
        box = self._page("Bluetooth", self.b_switch)
        self.b_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.b_list, 230), False, False, 0)
        foot = Gtk.Box()
        foot.pack_end(button("chip", cb=lambda: self._settings("bluetooth"), text="Añadir dispositivo"),
                      False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_bt(self):
        c = self.core
        b = c.bt
        self._set_switch(self.b_switch, b.powered)
        clear(self.b_list)
        if not b.available:
            self._empty(self.b_list, "No hay adaptador Bluetooth")
        elif not b.powered:
            self._empty(self.b_list, "Bluetooth desactivado")
        else:
            for d in sorted(b.devices.values(), key=lambda d: (not d["connected"], d["name"].lower())):
                sub = ("Conectando…" if d["path"] in b.busy else "Conectado" if d["connected"] else
                       "Desconectado · clic para conectar")
                if d["connected"] and d["battery"] is not None:
                    sub += f" · {d['battery']}%"
                self.b_list.pack_start(self._row(d["icon"], d["name"], sub,
                                                 lambda p=d["path"]: b.toggle_device(p),
                                                 sub_accent="blue" if d["connected"] else None),
                                       False, False, 0)
            if not b.devices:
                self._empty(self.b_list, "No hay dispositivos vinculados")
        self.b_list.show_all()

    def _open_bt(self):
        self.core.bt.refresh()
