"""Redes Wi-Fi."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import page


class WifiPage:
    PAGES = {
        "wifi": page("_build_wifi", "_fill_wifi", ("wifi",), "_open_wifi"),
    }

    def _build_wifi(self):
        self.w_switch = self._switch(self.core.wifi.set_enabled)
        box = self._page("Wi-Fi", self.w_switch)
        self.w_status = label("", "dim")
        box.pack_start(self.w_status, False, False, 0)
        self.w_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self._scroller(self.w_list, 230), False, False, 0)
        self.w_pw = Gtk.Box(spacing=8)
        self.w_entry = Gtk.Entry(hexpand=True, visibility=False)
        self.w_entry.connect("activate", lambda *_: self._wifi_password())
        self.w_pw.pack_start(self.w_entry, True, True, 0)
        self.w_pw.pack_start(button("chip", cb=self._wifi_password, text="Conectar"), False, False, 0)
        self.w_pw.set_no_show_all(True)
        box.pack_start(self.w_pw, False, False, 0)
        foot = Gtk.Box(spacing=8)
        foot.pack_start(button("chip", cb=self.core.wifi.scan, text="Buscar redes"), False, False, 0)
        foot.pack_end(button("chip", cb=lambda: self._settings("wifi"), text="Más ajustes"), False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def _fill_wifi(self):
        c = self.core
        w = c.wifi
        self._set_switch(self.w_switch, w.enabled)
        status = ("Conectado a " + w.active) if w.active else ("Conectado por cable" if w.wired else
                                                               ("Sin conexión" if w.enabled else "Wi-Fi desactivado"))
        if w.busy:
            status = f"Conectando a {w.busy}…"
        self.w_status.set_text(w.error or status)
        set_accent(self.w_status, "red" if w.error else None)
        clear(self.w_list)
        if w.enabled:
            for n in w.nets:
                q = ("excellent" if n["signal"] > 75 else "good" if n["signal"] > 50 else
                     "ok" if n["signal"] > 25 else "weak")
                sub = "Conectada" if n["inuse"] else ("Guardada" if n["ssid"] in w.known else
                                                      ("Protegida" if n["secure"] else "Abierta"))
                extra = [icon("changes-prevent-symbolic")] if n["secure"] else []
                cb = None if n["inuse"] else (lambda n=n: c.wifi.connect(n, on_need_password=self._need_password))
                self.w_list.pack_start(self._row(f"network-wireless-signal-{q}-symbolic", n["ssid"], sub, cb,
                                                 extra, sub_accent="blue" if n["inuse"] else None),
                                       False, False, 0)
            if not w.nets:
                self._empty(self.w_list, "Buscando redes…" if w.scanning else "No se encontraron redes")
        self.w_list.show_all()

    def _wifi_password(self):
        if self.pw_net:
            self.core.wifi.connect(self.pw_net, password=self.w_entry.get_text())
            self.w_entry.set_text("")
            self.pw_net = None
            self.w_pw.hide()

    def _need_password(self, net):
        self.pw_net = net
        self.w_entry.set_placeholder_text(f"Contraseña de «{net['ssid']}»")
        self.w_pw.show_all()
        self.w_entry.grab_focus()
        self.refresh()

    def _open_wifi(self):
        self.core.wifi.refresh()
        self.core.wifi.scan()
