"""Red: velocidad en vivo, interfaz, IP local, VPN e Internet."""
from ..common import *  # noqa: F401,F403
from ..widgets import *  # noqa: F401,F403
from ..services import *  # noqa: F401,F403
from .registry import feature, page, tool

feature("netmon", "Red y VPN", "Velocidad de bajada y subida, VPN activa y aviso si se cae Internet o la VPN")


class NetworkPage:
    PAGES = {
        "network": page("_build_network", "_fill_network", ("netmon",)),
    }
    TOOLS = (tool("network-transmit-receive-symbolic", "Red", "Velocidad, VPN e Internet", "network",
                  feature="netmon"),)

    def _build_network(self):
        box = self._page("Red")
        grid = Gtk.Grid(column_spacing=6, column_homogeneous=True)
        self.nt = {}
        for i, (key, title, color) in enumerate((("down", "↓ Bajada", (0.19, 0.82, 0.35)),
                                                 ("up", "↑ Subida", (0.04, 0.52, 1.0)))):
            t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t.get_style_context().add_class("wtile")
            t.pack_start(label(title, "dim small"), False, False, 0)
            v = label("—", "title")
            t.pack_start(v, False, False, 0)
            sp = Spark(color)
            t.pack_start(sp, False, False, 0)
            self.nt[key] = (v, sp)
            grid.attach(t, i, 0, 1, 1)
        box.pack_start(grid, False, False, 0)
        self.nt_rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.pack_start(self.nt_rows, False, False, 0)
        return box

    def _fill_network(self):
        n = self.core.netmon
        peak = max(list(n.down) + list(n.up) + [64 * 1024])
        for key, series in (("down", n.down), ("up", n.up)):
            v, sp = self.nt[key]
            v.set_text(fmt_rate(series[-1]) if series else "—")
            sp.set_values(series, 0, peak)
        clear(self.nt_rows)
        wifi = self.core.wifi.active
        rows = (("Internet", "Conectado" if n.online else "Sin Internet" if n.online is False else "…",
                 "green" if n.online else "red" if n.online is False else None),
                ("Conexión", (f"Wi-Fi {wifi} · " if wifi else "") + (n.iface or "ninguna"), None),
                ("IP local", n.ip or "—", None),
                ("VPN", ", ".join(n.vpns) if n.vpns else "Sin VPN", "blue" if n.vpns else None))
        for title, value, acc in rows:
            r = Gtk.Box(spacing=8)
            r.pack_start(label(title, "dim"), False, False, 0)
            v = label(value, "subtitle", xalign=1.0)
            set_accent(v, acc)
            r.pack_end(v, True, True, 0)
            self.nt_rows.pack_start(r, False, False, 0)
        self.nt_rows.show_all()
